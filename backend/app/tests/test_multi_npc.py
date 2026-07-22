"""Multi-NPC generality tests (P2). Pure — no Neo4j and no Ollama.

Proves the core NEKG game-design claim: the SAME evidence has a DIFFERENT
function per NPC, each NPC has isolated psychology, and each NPC's buried secret
never leaks — all on the same data-driven engine that runs Mara.
"""

from __future__ import annotations

from app.services import rules_engine as rx
from app.services.case_loader import load_case
from app.services.rules_engine import (
    Action,
    GameState,
    Intent,
    apply_result,
    compute_reveal_scope,
    evaluate_action,
    evaluate_intent,
)


def _discover_clock(state: GameState) -> None:
    apply_result(state, evaluate_action(state, Action.EXAMINE_CLOCK))


# --- The case now defines two NPCs on the same engine ----------------------- #
def test_case_defines_two_npcs():
    case = load_case("room_314")
    assert rx.NPC_MARA in case.npcs
    assert rx.NPC_TOMAS in case.npcs
    assert case.default_npc == rx.NPC_MARA


# --- Same evidence, different function --------------------------------------- #
def test_bell_evidence_gates_passage_for_tomas():
    # Without the clock evidence, Tomás does not reveal the passage.
    state = GameState()
    before = evaluate_intent(state, "ask_bell", npc_id=rx.NPC_TOMAS)
    assert rx.FACT_PASSAGE not in before.new_facts
    assert before.npc_id == rx.NPC_TOMAS

    # With the SAME clock evidence Mara uses, Tomás reveals the passage instead.
    _discover_clock(state)
    after = evaluate_intent(state, "ask_bell", npc_id=rx.NPC_TOMAS)
    assert after.allowed
    assert rx.FACT_PASSAGE in after.new_facts


def test_same_clock_evidence_different_function_across_npcs():
    state = GameState()
    _discover_clock(state)

    mara = evaluate_intent(state, Intent.ASK_ROOM_314, npc_id=rx.NPC_MARA)
    tomas = evaluate_intent(state, "ask_bell", npc_id=rx.NPC_TOMAS)

    # Mara -> "awake"; Tomás -> "passage". Neither leaks into the other.
    assert rx.FACT_MARA_AWAKE in mara.new_facts
    assert rx.FACT_PASSAGE not in mara.new_facts
    assert rx.FACT_PASSAGE in tomas.new_facts
    assert rx.FACT_MARA_AWAKE not in tomas.new_facts


# --- Each NPC's buried secret never leaks ------------------------------------ #
def test_tomas_secret_never_released():
    # Try every Tomás intent across a progressed state.
    state = GameState()
    _discover_clock(state)
    for trigger in ("ask_bell", "ask_daughter", "small_talk", "unknown"):
        result = evaluate_intent(state, trigger, npc_id=rx.NPC_TOMAS)
        assert rx.FACT_TOMAS_SECRET not in result.new_facts
        # And it is always in the forbidden reveal scope.
        _, forbidden = compute_reveal_scope(state, trigger, result, npc_id=rx.NPC_TOMAS)
        assert rx.FACT_TOMAS_SECRET in forbidden


def test_mara_secret_absent_from_tomas_scope_and_vice_versa():
    state = GameState()
    _discover_clock(state)

    tomas = evaluate_intent(state, "ask_bell", npc_id=rx.NPC_TOMAS)
    allowed_t, forbidden_t = compute_reveal_scope(state, "ask_bell", tomas, npc_id=rx.NPC_TOMAS)
    # Tomás's scope guards HIS secret, not Mara's.
    assert rx.FACT_TOMAS_SECRET in forbidden_t
    assert rx.FACT_MARA_ALLOWED_ENTRY not in allowed_t


# --- Per-NPC psychology is isolated ------------------------------------------ #
def test_npc_stats_are_isolated():
    state = GameState()
    state.npc_stats[rx.NPC_TOMAS] = {"trust": 40, "fear": 30, "guilt": 20, "sanity": 65, "occult_exposure": 25}
    _discover_clock(state)

    mara_fear_before = state.mara["fear"]
    tomas_fear_before = state.npc_stats[rx.NPC_TOMAS]["fear"]

    result = evaluate_intent(state, "ask_bell", npc_id=rx.NPC_TOMAS)
    assert result.allowed
    apply_result(state, result)

    # Tomás's fear moved (delta fear: 8); Mara's did not.
    assert state.npc_stats[rx.NPC_TOMAS]["fear"] == tomas_fear_before + 8
    assert state.mara["fear"] == mara_fear_before


# --- Mara's flow is unchanged by the multi-NPC refactor ---------------------- #
def test_mara_flow_still_targets_mara():
    state = GameState()
    _discover_clock(state)
    result = evaluate_intent(state, Intent.ASK_ROOM_314)
    assert result.npc_id == rx.NPC_MARA
    apply_result(state, result)
    assert rx.FACT_MARA_AWAKE in state.known_facts
    # Confront delta applies to Mara.
    apply_result(state, evaluate_action(state, Action.EXAMINE_LEDGER))
    trust_before = state.mara["trust"]
    confront = evaluate_intent(state, Intent.CONFRONT_MARA)
    apply_result(state, confront)
    assert state.mara["trust"] == trust_before + 15
