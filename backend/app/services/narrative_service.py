"""Narrative orchestration: actions, dialogue, and API response assembly.

Flow (see docs/architecture.md):
  player action/intent -> rule engine -> Neo4j state -> contextual retrieval
  -> LLM language -> validation -> claim/trace persistence -> frontend.
"""

from __future__ import annotations

from app.models import (
    ActionOption,
    ActionResponse,
    DialogueChip,
    DialogueResponse,
    EndingModel,
    EvidenceModel,
    FactModel,
    GameStateResponse,
    LLMResponse,
    MaraView,
    SceneModel,
    TraceModel,
)
from app.services import rules_engine as rx
from app.services import trace_service
from app.services.llm_service import BaseLLMService, PromptContext, validate_llm_response
from app.services.neo4j_service import Neo4jService
from app.services.rules_engine import Action, GameState, Intent, RuleResult

LOCATION_LABELS = {
    rx.LOC_RECEPTION: "Recepção",
    rx.LOC_CORRIDOR: "Corredor",
    rx.LOC_ROOM_314: "Quarto 314",
}

SCENE_TEXT = {
    rx.LOC_RECEPTION: (
        "A recepção da Pensão Vesper. A chuva castiga as janelas. Um relógio de "
        "parede parado, velas trêmulas e um livro de hóspedes aberto sobre o balcão. "
        "Mara observa você em silêncio."
    ),
    rx.LOC_CORRIDOR: (
        "O corredor do terceiro andar. O ar é frio e cheira a maresia. Ao fundo, a "
        "porta do quarto 314 — selada há dez anos — parece pulsar com uma luz fraca, "
        "azul-esverdeada."
    ),
    rx.LOC_ROOM_314: "O quarto 314. Não deve ser resolvido nesta investigação.",
}


def _derive_emotion(mara: dict[str, int]) -> str:
    if mara.get("fear", 0) >= 70:
        return "fearful"
    if mara.get("guilt", 0) >= 70:
        return "guilty"
    if mara.get("trust", 0) >= 60:
        return "relieved"
    return "guarded"


# --------------------------------------------------------------------------- #
# Response assembly
# --------------------------------------------------------------------------- #


def _build_actions(state: GameState) -> list[ActionOption]:
    actions: list[ActionOption] = []
    if state.location == rx.LOC_RECEPTION:
        actions.append(ActionOption(action="examine_clock", label="Examinar relógio", enabled=True))
        actions.append(ActionOption(action="examine_ledger", label="Examinar livro de hóspedes", enabled=True))
        actions.append(
            ActionOption(
                action="enter_corridor",
                label="Subir ao corredor",
                enabled=state.corridor_unlocked,
                reason=None if state.corridor_unlocked else "O corredor está trancado. Peça a chave a Mara.",
            )
        )
    elif state.location == rx.LOC_CORRIDOR:
        actions.append(
            ActionOption(
                action="examine_door",
                label="Examinar a porta 314",
                enabled=state.has_key(),
                reason=None if state.has_key() else "Você precisa da chave do corredor.",
            )
        )
    return actions


def _build_chips(state: GameState) -> list[DialogueChip]:
    has_clock = rx.EV_CLOCK in state.discovered_evidence
    has_ledger = rx.EV_LEDGER in state.discovered_evidence
    saw_figure = rx.FACT_MARA_SAW_FIGURE in state.known_facts
    return [
        DialogueChip(intent="ask_room_314", label="Quem entrou no quarto 314?", enabled=True),
        DialogueChip(
            intent="ask_clock",
            label="Por que o relógio parou às 02:17?",
            enabled=has_clock,
            reason=None if has_clock else "Examine o relógio primeiro.",
        ),
        DialogueChip(
            intent="ask_elian",
            label="Fale sobre Elian Voss.",
            enabled=has_ledger,
            reason=None if has_ledger else "Examine o livro de hóspedes primeiro.",
        ),
        DialogueChip(
            intent="confront_mara",
            label="Você está escondendo algo.",
            enabled=has_clock and has_ledger,
            reason=None if (has_clock and has_ledger) else "Reúna o relógio e o livro.",
        ),
        DialogueChip(
            intent="request_key",
            label="Entregue a chave.",
            enabled=saw_figure,
            reason=None if saw_figure else "Confronte Mara primeiro.",
        ),
    ]


async def build_state_response(
    neo4j: Neo4jService,
    sid: str,
    player_id: str,
    state: GameState,
    *,
    last_line: str | None = None,
    emotion: str | None = None,
) -> GameStateResponse:
    ev_cat = await neo4j.evidence_catalog()
    fact_cat = await neo4j.fact_catalog()

    discovered = [
        EvidenceModel(
            id=eid,
            name=ev_cat.get(eid, {}).get("name", eid),
            description=ev_cat.get(eid, {}).get("description", ""),
        )
        for eid in sorted(state.discovered_evidence)
    ]
    # Never surface the buried secret, even defensively.
    known = [
        FactModel(id=fid, statement=fact_cat.get(fid, {}).get("statement", fid))
        for fid in sorted(state.known_facts)
        if fid != rx.FACT_MARA_ALLOWED_ENTRY
    ]

    ending = None
    if state.ended:
        ending = EndingModel(
            title="A porta se abre",
            lines=["A porta se abre sozinha.", "Ao longe, o sino toca uma vez."],
        )

    return GameStateResponse(
        session_id=sid,
        player_id=player_id,
        scene=SceneModel(
            location=state.location,
            name=LOCATION_LABELS.get(state.location, state.location),
            description=SCENE_TEXT.get(state.location, ""),
        ),
        location_label=LOCATION_LABELS.get(state.location, state.location),
        actions=_build_actions(state),
        dialogue_chips=_build_chips(state),
        mara=MaraView(emotion=emotion or _derive_emotion(state.mara), last_line=last_line),
        discovered_evidence=discovered,
        known_facts=known,
        ended=state.ended,
        ending=ending,
    )


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #


async def handle_action(neo4j: Neo4jService, sid: str, action_value: str) -> ActionResponse:
    player_id, state = await neo4j.get_game_state(sid)
    action = Action(action_value)
    result: RuleResult = rx.evaluate_action(state, action)

    if result.allowed:
        rx.apply_result(state, result)
        await neo4j.persist_state(sid, state)

    trace = trace_service.build_action_trace(result, action_value)
    await neo4j.save_action_trace(sid, trace.model_dump())

    state_resp = await build_state_response(neo4j, sid, player_id, state)
    message = result.narration if (result.allowed and result.narration) else result.reason

    return ActionResponse(
        session_id=sid,
        action=action_value,
        allowed=result.allowed,
        message=message,
        events=list(result.events),
        state=state_resp,
        trace=trace,
    )


# --------------------------------------------------------------------------- #
# Dialogue
# --------------------------------------------------------------------------- #


def _to_intent(value: str | None) -> tuple[Intent, bool]:
    """Return (intent, is_valid). Unknown/invalid map to Intent.UNKNOWN."""

    if not value:
        return Intent.UNKNOWN, False
    try:
        return Intent(value), True
    except ValueError:
        return Intent.UNKNOWN, False


def _fallback_response(intent: Intent, state: GameState, result: RuleResult) -> LLMResponse:
    """Deterministic PT-BR fallback. Never references fact ids (always in-scope)."""

    has_clock = rx.EV_CLOCK in state.discovered_evidence
    has_ledger = rx.EV_LEDGER in state.discovered_evidence
    saw_figure = rx.FACT_MARA_SAW_FIGURE in state.known_facts
    emotion = _derive_emotion(state.mara)

    if intent == Intent.ASK_ROOM_314:
        line = (
            "Eu estava acordada quando o sino tocou. Mas o quarto 314... não peça para eu falar dele."
            if has_clock
            else "Não há nada no 314. Está fechado há anos. Deixe isso para lá."
        )
        claim = "uncertain_memory" if has_clock else "evasion"
    elif intent == Intent.ASK_CLOCK:
        line = (
            "O relógio parou às 02:17. Foi a hora do sino. Eu lembro."
            if has_clock
            else "Esse relógio está morto há tempos. Não sei dizer."
        )
        claim = "truth" if has_clock else "evasion"
    elif intent == Intent.ASK_ELIAN:
        line = (
            "Elian Voss sumiu faz dez anos. Prefiro não remexer nisso."
            if has_ledger
            else "Não me lembro desse nome. Muita gente passa por aqui."
        )
        claim = "uncertain_memory" if has_ledger else "lie"
    elif intent == Intent.CONFRONT_MARA:
        line = (
            "Chega. Eu vi uma figura entrar no 314. Uma luz esverdeada. Foi tudo tão rápido."
            if (has_clock and has_ledger)
            else "Você não tem provas. Só medo, como eu."
        )
        claim = "truth" if (has_clock and has_ledger) else "evasion"
    elif intent == Intent.REQUEST_KEY:
        line = (
            "Tome a chave do corredor. Mas não diga que eu não avisei."
            if saw_figure
            else "Não vou lhe dar chave nenhuma. Ainda não."
        )
        claim = "truth" if saw_figure else "evasion"
    elif intent == Intent.SMALL_TALK:
        line = "A tempestade vai passar. Ou não. Fique onde eu possa ver você."
        claim = "truth"
    else:
        line = "Não sei o que você quer dizer. Seja claro, detetive."
        claim = "evasion"

    move = result.allowed and (result.new_facts or result.granted_items)
    suggested = "reveal_figure" if intent == Intent.CONFRONT_MARA and move else "evade"

    return LLMResponse(
        line=line,
        emotion=emotion,  # type: ignore[arg-type]
        suggested_intent=suggested,  # type: ignore[arg-type]
        claim_type=claim,  # type: ignore[arg-type]
        fact_ids_referenced=[],
        state_delta_suggestion={"trust": 0, "fear": 0, "guilt": 0, "sanity": 0},  # type: ignore[arg-type]
    )


async def handle_dialogue(
    neo4j: Neo4jService,
    llm: BaseLLMService,
    sid: str,
    text: str | None,
    intent_value: str | None,
) -> DialogueResponse:
    # 1. Determine intent (classify free text if needed) — Rule R7.
    classified_from_text = False
    if intent_value:
        intent, _ = _to_intent(intent_value)
    else:
        classified = await llm.classify_intent(text or "")
        intent, _ = _to_intent(classified)
        classified_from_text = True

    # 2. Contextual retrieval (minimal, policy-filtered subgraph).
    context = await neo4j.get_dialogue_context(sid, intent)
    state: GameState = context["game_state"]
    player_id: str = context["player_id"]
    result: RuleResult = context["rule_result"]
    allowed_fact_ids: list[str] = context["allowed_fact_ids"]
    forbidden_fact_ids: list[str] = context["forbidden_fact_ids"]
    allowed_moves: list[str] = context["allowed_suggested_intents"]

    # 3. Build the constrained prompt context and call the language layer.
    prompt_ctx = PromptContext(
        intent=intent.value,
        allowed_facts=context["allowed_facts"],
        allowed_fact_ids=allowed_fact_ids,
        forbidden_fact_ids=forbidden_fact_ids,
        allowed_suggested_intents=allowed_moves,
        mara_state=dict(state.mara),
        emotion_hint=_derive_emotion(state.mara),
        has_clock=rx.EV_CLOCK in state.discovered_evidence,
        has_ledger=rx.EV_LEDGER in state.discovered_evidence,
        knows_saw_figure=rx.FACT_MARA_SAW_FIGURE in state.known_facts,
        rule_allowed=result.allowed,
    )

    source = llm.source
    validation = "ok"
    try:
        raw = await llm.generate(prompt_ctx)
        valid, resp, validation = validate_llm_response(raw, allowed_fact_ids)
    except Exception:
        valid, resp, validation = False, None, "llm_error"

    # 4. Fallback on any invalid/failed generation (Rule R8 safety net).
    if not valid or resp is None:
        resp = _fallback_response(intent, state, result)
        source = "fallback"

    # 5. Apply the deterministic rule and persist state (only the engine writes).
    if result.allowed:
        rx.apply_result(state, result)
        await neo4j.persist_state(sid, state)

    # 6. Persist claim + trace.
    about_fact = resp.fact_ids_referenced[0] if resp.fact_ids_referenced else None
    trace: TraceModel = trace_service.build_dialogue_trace(
        result=result,
        intent=intent.value,
        classified_from_text=classified_from_text,
        allowed_fact_ids=allowed_fact_ids,
        forbidden_fact_ids=forbidden_fact_ids,
        allowed_intents=allowed_moves,
        claim_type=resp.claim_type,
        llm_source=source,
        validation=validation,
    )
    await neo4j.save_claim_and_trace(
        sid,
        claim_text=resp.line,
        truth_status=resp.claim_type,
        intent=intent.value,
        trace=trace.model_dump(),
        about_fact=about_fact,
    )

    # 7. Build the refreshed game state for the frontend.
    state_resp = await build_state_response(
        neo4j, sid, player_id, state, last_line=resp.line, emotion=resp.emotion
    )

    return DialogueResponse(
        session_id=sid,
        intent=intent.value,
        mara_line=resp.line,
        emotion=resp.emotion,
        claim_type=resp.claim_type,
        state=state_resp,
        trace=trace,
    )
