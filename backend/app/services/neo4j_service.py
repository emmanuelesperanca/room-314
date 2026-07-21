"""Neo4j data-access layer for the NEKG.

All Cypher is fixed and parameterized — user text is NEVER concatenated into a
query (defends against injection). The frontend never talks to Neo4j directly;
only this backend does, using credentials from the environment.

Per-session mutable state (Player, Session, discovered evidence, Mara's
psychological deltas) lives on session-scoped nodes/relationships. Canonical
world nodes are shared and never mutated at runtime.
"""

from __future__ import annotations

import uuid

from neo4j import AsyncGraphDatabase

from app.config import Settings
from app.services import rules_engine as rx
from app.services.rules_engine import GameState, Intent, RuleResult


class Neo4jService:
    def __init__(self, settings: Settings) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._db = settings.neo4j_database
        self._evidence_catalog: dict[str, dict] | None = None
        self._fact_catalog: dict[str, dict] | None = None

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #

    async def close(self) -> None:
        await self._driver.close()

    async def verify(self) -> bool:
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def _read(self, query: str, **params) -> list[dict]:
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, **params)
            return await result.data()

    async def _write(self, query: str, **params) -> list[dict]:
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, **params)
            return await result.data()

    # --------------------------------------------------------------------- #
    # Canonical catalogs (immutable → cached in-process)
    # --------------------------------------------------------------------- #

    async def evidence_catalog(self) -> dict[str, dict]:
        if self._evidence_catalog is None:
            rows = await self._read(
                "MATCH (e:Evidence) RETURN e.id AS id, e.name AS name, e.description AS description"
            )
            self._evidence_catalog = {r["id"]: r for r in rows}
        return self._evidence_catalog

    async def fact_catalog(self) -> dict[str, dict]:
        if self._fact_catalog is None:
            rows = await self._read(
                "MATCH (f:Fact) RETURN f.id AS id, f.statement AS statement, "
                "f.canonical AS canonical, f.spoiler_level AS spoiler_level"
            )
            self._fact_catalog = {r["id"]: r for r in rows}
        return self._fact_catalog

    # --------------------------------------------------------------------- #
    # Session lifecycle
    # --------------------------------------------------------------------- #

    async def start_session(self) -> tuple[str, str, GameState]:
        sid = "sess_" + uuid.uuid4().hex[:12]
        pid = "player_" + uuid.uuid4().hex[:12]
        await self._write(
            """
            MATCH (mara:NPC {id:'mara_doyle'})
            MATCH (loc:Location {id:'reception'})
            CREATE (s:Session {
                id:$sid, created_at: toString(datetime()), location:'reception',
                mara_trust: mara.trust, mara_fear: mara.fear, mara_guilt: mara.guilt,
                mara_sanity: mara.sanity, mara_occult_exposure: mara.occult_exposure,
                has_key: false, corridor_unlocked: false, ended: false, last_rule: null
            })
            CREATE (p:Player {id:$pid, created_at: toString(datetime())})
            CREATE (s)-[:HAS_PLAYER]->(p)
            CREATE (s)-[:AT_LOCATION]->(loc)
            """,
            sid=sid,
            pid=pid,
        )
        _, state = await self.get_game_state(sid)
        return sid, pid, state

    async def session_exists(self, sid: str) -> bool:
        rows = await self._read(
            "MATCH (s:Session {id:$sid}) RETURN s.id AS id", sid=sid
        )
        return bool(rows)

    async def get_game_state(self, sid: str) -> tuple[str, GameState]:
        rows = await self._read(
            """
            MATCH (s:Session {id:$sid})-[:HAS_PLAYER]->(p:Player)
            OPTIONAL MATCH (p)-[:DISCOVERED]->(e:Evidence)
            OPTIONAL MATCH (p)-[:KNOWS_FACT]->(f:Fact)
            RETURN s{.*} AS s, p.id AS player_id,
                   collect(DISTINCT e.id) AS evidence,
                   collect(DISTINCT f.id) AS facts
            """,
            sid=sid,
        )
        if not rows:
            raise KeyError(sid)
        row = rows[0]
        s = row["s"]
        evidence = {e for e in row["evidence"] if e}
        facts = {f for f in row["facts"] if f}
        inventory: set[str] = set()
        if s.get("has_key"):
            inventory.add(rx.ITEM_KEY)
        state = GameState(
            session_id=sid,
            location=s["location"],
            discovered_evidence=evidence,
            known_facts=facts,
            inventory=inventory,
            corridor_unlocked=bool(s.get("corridor_unlocked")),
            ended=bool(s.get("ended")),
            last_rule=s.get("last_rule"),
            mara={
                "trust": int(s["mara_trust"]),
                "fear": int(s["mara_fear"]),
                "guilt": int(s["mara_guilt"]),
                "sanity": int(s["mara_sanity"]),
                "occult_exposure": int(s["mara_occult_exposure"]),
            },
        )
        return row["player_id"], state

    async def persist_state(self, sid: str, state: GameState) -> None:
        # 1. Scalar session properties.
        await self._write(
            """
            MATCH (s:Session {id:$sid})
            SET s.location=$location,
                s.mara_trust=$trust, s.mara_fear=$fear, s.mara_guilt=$guilt,
                s.mara_sanity=$sanity, s.mara_occult_exposure=$occult,
                s.has_key=$has_key, s.corridor_unlocked=$corridor_unlocked,
                s.ended=$ended, s.last_rule=$last_rule
            """,
            sid=sid,
            location=state.location,
            trust=state.mara["trust"],
            fear=state.mara["fear"],
            guilt=state.mara["guilt"],
            sanity=state.mara["sanity"],
            occult=state.mara["occult_exposure"],
            has_key=state.has_key(),
            corridor_unlocked=state.corridor_unlocked,
            ended=state.ended,
            last_rule=state.last_rule,
        )
        # 2. Current location relationship.
        await self._write(
            """
            MATCH (s:Session {id:$sid})
            OPTIONAL MATCH (s)-[r:AT_LOCATION]->()
            DELETE r
            WITH s
            MATCH (loc:Location {id:$location})
            CREATE (s)-[:AT_LOCATION]->(loc)
            """,
            sid=sid,
            location=state.location,
        )
        # 3. Discovered evidence (per session).
        if state.discovered_evidence:
            await self._write(
                """
                MATCH (s:Session {id:$sid})-[:HAS_PLAYER]->(p:Player)
                UNWIND $ids AS eid
                MATCH (e:Evidence {id:eid})
                MERGE (p)-[:DISCOVERED]->(e)
                """,
                sid=sid,
                ids=list(state.discovered_evidence),
            )
        # 4. Known facts (per session).
        if state.known_facts:
            await self._write(
                """
                MATCH (s:Session {id:$sid})-[:HAS_PLAYER]->(p:Player)
                UNWIND $ids AS fid
                MATCH (f:Fact {id:fid})
                MERGE (p)-[:KNOWS_FACT]->(f)
                """,
                sid=sid,
                ids=list(state.known_facts),
            )

    async def save_claim_and_trace(
        self,
        sid: str,
        *,
        claim_text: str,
        truth_status: str,
        intent: str,
        trace: dict,
        about_fact: str | None,
    ) -> None:
        cid = "claim_" + uuid.uuid4().hex[:12]
        tid = "trace_" + uuid.uuid4().hex[:12]
        await self._write(
            """
            MATCH (s:Session {id:$sid}), (mara:NPC {id:'mara_doyle'})
            CREATE (c:Claim {
                id:$cid, text:$claim_text, truth_status:$truth_status,
                intent:$intent, created_at: toString(datetime())
            })
            CREATE (mara)-[:MADE_CLAIM]->(c)
            CREATE (t:Trace {
                id:$tid, created_at: toString(datetime()),
                rule_id:$rule_id, intent:$intent,
                facts_used:$facts_used, facts_hidden:$facts_hidden,
                allowed_intents:$allowed_intents, claim_type:$claim_type,
                reason:$reason, llm_source:$llm_source, validation:$validation
            })
            CREATE (s)-[:TRACE]->(t)
            CREATE (c)-[:HAS_TRACE]->(t)
            WITH c
            OPTIONAL MATCH (f:Fact {id:$about_fact})
            FOREACH (_ IN CASE WHEN f IS NULL THEN [] ELSE [1] END |
                CREATE (c)-[:ABOUT]->(f))
            """,
            sid=sid,
            cid=cid,
            tid=tid,
            claim_text=claim_text,
            truth_status=truth_status,
            intent=intent,
            rule_id=trace.get("rule_id"),
            facts_used=trace.get("facts_used", []),
            facts_hidden=trace.get("facts_hidden", []),
            allowed_intents=trace.get("allowed_intents", []),
            claim_type=trace.get("claim_type"),
            reason=trace.get("reason", ""),
            llm_source=trace.get("llm_source", "n/a"),
            validation=trace.get("validation", "n/a"),
            about_fact=about_fact,
        )

    async def save_action_trace(self, sid: str, trace: dict) -> None:
        tid = "trace_" + uuid.uuid4().hex[:12]
        await self._write(
            """
            MATCH (s:Session {id:$sid})
            CREATE (t:Trace {
                id:$tid, created_at: toString(datetime()),
                rule_id:$rule_id, intent:$intent,
                facts_used:$facts_used, facts_hidden:$facts_hidden,
                allowed_intents:$allowed_intents, claim_type:$claim_type,
                reason:$reason, llm_source:$llm_source, validation:$validation
            })
            CREATE (s)-[:TRACE]->(t)
            """,
            sid=sid,
            tid=tid,
            rule_id=trace.get("rule_id"),
            intent=trace.get("action") or trace.get("intent"),
            facts_used=trace.get("facts_used", []),
            facts_hidden=trace.get("facts_hidden", []),
            allowed_intents=trace.get("allowed_intents", []),
            claim_type=trace.get("claim_type"),
            reason=trace.get("reason", ""),
            llm_source=trace.get("llm_source", "n/a"),
            validation=trace.get("validation", "n/a"),
        )

    # --------------------------------------------------------------------- #
    # Contextual retrieval for dialogue (NEKG subgraph selection)
    # --------------------------------------------------------------------- #

    async def get_dialogue_context(self, sid: str, intent: Intent) -> dict:
        """Select the minimal, policy-filtered subgraph for one dialogue turn.

        Never returns the whole graph. Never returns secret statements. Returns
        a human-readable selection trace explaining why the context was chosen.
        """

        player_id, state = await self.get_game_state(sid)
        result: RuleResult = rx.evaluate_intent(state, intent)
        allowed_ids, forbidden_ids = rx.compute_reveal_scope(state, intent, result)
        allowed_moves = rx.allowed_suggested_intents(state, intent)

        fact_cat = await self.fact_catalog()
        allowed_facts = [
            {"id": fid, "statement": fact_cat[fid]["statement"]}
            for fid in allowed_ids
            if fid in fact_cat
        ]

        # Secrets: ids + policy only — NEVER the secret statement.
        secrets = await self._read(
            """
            MATCH (:NPC {id:'mara_doyle'})-[c:CONCEALS]->(f:Fact)
            RETURN f.id AS id, c.motive AS motive, c.reveal_policy AS reveal_policy
            """
        )

        # Hypotheses: non-canonical, clearly marked.
        hypotheses = await self._read(
            """
            MATCH (:NPC {id:'mara_doyle'})-[b:BELIEVES]->(h:Hypothesis)
            RETURN h.id AS id, h.statement AS statement, b.certainty AS certainty
            """
        )
        for h in hypotheses:
            h["canonical"] = False

        selection_trace = self._selection_trace(state, intent, result, allowed_ids, forbidden_ids)

        return {
            "player_id": player_id,
            "game_state": state,
            "rule_result": result,
            "allowed_fact_ids": allowed_ids,
            "forbidden_fact_ids": forbidden_ids,
            "allowed_facts": allowed_facts,
            "allowed_suggested_intents": allowed_moves,
            "secrets": secrets,
            "hypotheses": hypotheses,
            "selection_trace": selection_trace,
        }

    @staticmethod
    def _selection_trace(
        state: GameState,
        intent: Intent,
        result: RuleResult,
        allowed_ids: list[str],
        forbidden_ids: list[str],
    ) -> list[str]:
        trace: list[str] = [f"Intenção avaliada: {intent.value} → regra {result.rule_id}."]
        if rx.EV_CLOCK in state.discovered_evidence:
            trace.append("Evidência do relógio descoberta → fatos sobre 02:17 podem ser liberados.")
        else:
            trace.append("Relógio ainda não examinado → fatos sobre 02:17 permanecem ocultos.")
        if rx.EV_LEDGER in state.discovered_evidence:
            trace.append("Livro de hóspedes descoberto → Elian Voss pode ser mencionado.")
        if rx.FACT_MARA_SAW_FIGURE in state.known_facts:
            trace.append("Figura já revelada → chave pode ser negociada.")
        trace.append("mara_allowed_entry está SEMPRE nos fatos proibidos.")
        trace.append(f"Fatos permitidos: {allowed_ids or '[nenhum]'}.")
        trace.append(f"Fatos proibidos: {forbidden_ids}.")
        return trace

    # --------------------------------------------------------------------- #
    # Debug / audit
    # --------------------------------------------------------------------- #

    async def get_last_trace(self, sid: str) -> dict | None:
        rows = await self._read(
            """
            MATCH (s:Session {id:$sid})-[:TRACE]->(t:Trace)
            RETURN t{.*} AS t
            ORDER BY t.created_at DESC
            LIMIT 1
            """,
            sid=sid,
        )
        return rows[0]["t"] if rows else None

    async def get_relationship_summary(self, sid: str) -> list[str]:
        summary: list[str] = []
        knows = await self._read(
            """
            MATCH (:NPC {id:'mara_doyle'})-[k:KNOWS]->(f:Fact)
            RETURN f.id AS id, k.certainty AS certainty, k.reveal_policy AS policy
            ORDER BY f.id
            """
        )
        for r in knows:
            summary.append(
                f"Mara KNOWS {r['id']} (certeza {r['certainty']}, política {r['policy']})"
            )
        conceals = await self._read(
            """
            MATCH (:NPC {id:'mara_doyle'})-[c:CONCEALS]->(f:Fact)
            RETURN f.id AS id, c.motive AS motive, c.reveal_policy AS policy
            ORDER BY f.id
            """
        )
        for r in conceals:
            summary.append(
                f"Mara CONCEALS {r['id']} (motivo: {r['motive']}, política {r['policy']})"
            )
        supports = await self._read(
            """
            MATCH (e:Evidence)-[s:SUPPORTS]->(f:Fact)
            RETURN e.id AS ev, f.id AS fact, s.weight AS weight
            ORDER BY e.id
            """
        )
        for r in supports:
            summary.append(f"{r['ev']} SUPPORTS {r['fact']} (peso {r['weight']})")
        player = await self._read(
            """
            MATCH (s:Session {id:$sid})-[:HAS_PLAYER]->(p:Player)
            OPTIONAL MATCH (p)-[:DISCOVERED]->(e:Evidence)
            OPTIONAL MATCH (p)-[:KNOWS_FACT]->(f:Fact)
            RETURN collect(DISTINCT e.id) AS ev, collect(DISTINCT f.id) AS facts
            """,
            sid=sid,
        )
        if player:
            ev = [x for x in player[0]["ev"] if x]
            facts = [x for x in player[0]["facts"] if x]
            summary.append(f"Player DISCOVERED {ev or '[nenhuma]'}")
            summary.append(f"Player KNOWS_FACT {facts or '[nenhum]'}")
        return summary
