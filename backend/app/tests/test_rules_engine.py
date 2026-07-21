"""Deterministic rule-engine tests. No Neo4j and no Ollama required."""

from __future__ import annotations

from app.models import LLMResponse
from app.services import rules_engine as rx
from app.services.llm_service import validate_llm_response
from app.services.rules_engine import Action, GameState, Intent, apply_result, evaluate_action, evaluate_intent


def _state_with(**kwargs) -> GameState:
    state = GameState()
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def _examine(state: GameState, action: Action) -> None:
    result = evaluate_action(state, action)
    assert result.allowed
    apply_result(state, result)


# 1. Before examining the clock, asking about 314 cannot release mara_awake_0217.
def test_ask_314_before_clock_does_not_release_awake():
    state = GameState()
    result = evaluate_intent(state, Intent.ASK_ROOM_314)
    assert rx.FACT_MARA_AWAKE not in result.new_facts
    apply_result(state, result)
    assert rx.FACT_MARA_AWAKE not in state.known_facts


# 2. After examining the clock, asking about 314 can release mara_awake_0217.
def test_ask_314_after_clock_releases_awake():
    state = GameState()
    _examine(state, Action.EXAMINE_CLOCK)
    assert rx.EV_CLOCK in state.discovered_evidence
    result = evaluate_intent(state, Intent.ASK_ROOM_314)
    assert rx.FACT_MARA_AWAKE in result.new_facts
    apply_result(state, result)
    assert rx.FACT_MARA_AWAKE in state.known_facts


# 3. confront_mara without BOTH evidences is blocked.
def test_confront_without_both_evidences_blocked():
    state = GameState()
    _examine(state, Action.EXAMINE_CLOCK)  # only the clock
    result = evaluate_intent(state, Intent.CONFRONT_MARA)
    assert result.allowed is False
    assert rx.FACT_MARA_SAW_FIGURE not in result.new_facts


# 4. confront_mara with clock + ledger releases mara_saw_figure.
def test_confront_with_both_evidences_releases_figure():
    state = GameState()
    _examine(state, Action.EXAMINE_CLOCK)
    _examine(state, Action.EXAMINE_LEDGER)
    result = evaluate_intent(state, Intent.CONFRONT_MARA)
    assert result.allowed is True
    assert rx.FACT_MARA_SAW_FIGURE in result.new_facts
    apply_result(state, result)
    assert rx.FACT_MARA_SAW_FIGURE in state.known_facts


# 5. request_key without mara_saw_figure is blocked.
def test_request_key_without_figure_blocked():
    state = GameState()
    _examine(state, Action.EXAMINE_CLOCK)
    _examine(state, Action.EXAMINE_LEDGER)
    result = evaluate_intent(state, Intent.REQUEST_KEY)
    assert result.allowed is False
    assert rx.ITEM_KEY not in result.granted_items


# 6. The final state only happens with key + corridor + examine_door.
def test_examine_door_requires_key_and_corridor():
    # Not in corridor, no key -> blocked.
    state = GameState()
    assert evaluate_action(state, Action.EXAMINE_DOOR).allowed is False

    # In corridor but without key -> still blocked.
    state_no_key = _state_with(location=rx.LOC_CORRIDOR)
    assert evaluate_action(state_no_key, Action.EXAMINE_DOOR).allowed is False

    # In corridor with key -> allowed, triggers ending.
    state_ok = _state_with(location=rx.LOC_CORRIDOR, inventory={rx.ITEM_KEY}, corridor_unlocked=True)
    result = evaluate_action(state_ok, Action.EXAMINE_DOOR)
    assert result.allowed is True
    assert "door_opens" in result.events
    apply_result(state_ok, result)
    assert state_ok.ended is True


# 7. No rule ever releases mara_allowed_entry (the buried secret).
def test_no_rule_releases_mara_allowed_entry():
    intents = list(Intent)
    actions = list(Action)

    # A fully-progressed state to exercise every unlocked branch.
    state = _state_with(
        location=rx.LOC_CORRIDOR,
        discovered_evidence={rx.EV_CLOCK, rx.EV_LEDGER},
        known_facts={rx.FACT_MARA_SAW_FIGURE, rx.FACT_FIGURE_LIGHT, rx.FACT_MARA_AWAKE},
        inventory={rx.ITEM_KEY},
        corridor_unlocked=True,
    )
    for intent in intents:
        result = evaluate_intent(state, intent)
        assert rx.FACT_MARA_ALLOWED_ENTRY not in result.new_facts
    for action in actions:
        result = evaluate_action(state, action)
        assert rx.FACT_MARA_ALLOWED_ENTRY not in result.new_facts

    # Even if forcibly injected, apply_result scrubs it.
    forced = evaluate_intent(GameState(), Intent.SMALL_TALK)
    forced.new_facts.append(rx.FACT_MARA_ALLOWED_ENTRY)
    s2 = GameState()
    apply_result(s2, forced)
    assert rx.FACT_MARA_ALLOWED_ENTRY not in s2.known_facts


# 9. The validator rejects an LLM response referencing a fact outside scope.
def test_validator_rejects_out_of_scope_fact():
    raw = {
        "line": "Eu vi tudo naquela noite.",
        "emotion": "guilty",
        "suggested_intent": "reveal_figure",
        "claim_type": "truth",
        "fact_ids_referenced": [rx.FACT_MARA_SAW_FIGURE],
        "state_delta_suggestion": {"trust": 0, "fear": 0, "guilt": 0, "sanity": 0},
    }
    # allowed scope does NOT include mara_saw_figure
    valid, resp, reason = validate_llm_response(raw, allowed_fact_ids=[rx.FACT_BELL_0217])
    assert valid is False
    assert resp is None
    assert reason == "fact_out_of_scope"


def test_validator_accepts_in_scope_fact():
    raw = {
        "line": "O sino tocou às 02:17.",
        "emotion": "guarded",
        "suggested_intent": "reveal_awake",
        "claim_type": "truth",
        "fact_ids_referenced": [rx.FACT_BELL_0217],
        "state_delta_suggestion": {"trust": 0, "fear": 0, "guilt": 0, "sanity": 0},
    }
    valid, resp, reason = validate_llm_response(raw, allowed_fact_ids=[rx.FACT_BELL_0217])
    assert valid is True
    assert isinstance(resp, LLMResponse)
    assert reason == "ok"


def test_validator_rejects_buried_secret_even_if_allowed():
    raw = {
        "line": "Eu deixei aquilo entrar.",
        "emotion": "guilty",
        "suggested_intent": "evade",
        "claim_type": "truth",
        "fact_ids_referenced": [rx.FACT_MARA_ALLOWED_ENTRY],
        "state_delta_suggestion": {"trust": 0, "fear": 0, "guilt": 0, "sanity": 0},
    }
    valid, _, reason = validate_llm_response(
        raw, allowed_fact_ids=[rx.FACT_MARA_ALLOWED_ENTRY]
    )
    assert valid is False
    assert reason == "forbidden_fact_referenced"


def test_word_limit_enforced_on_line():
    long_line = " ".join(["palavra"] * 60)
    resp = LLMResponse(
        line=long_line,
        emotion="guarded",
        suggested_intent="evade",
        claim_type="evasion",
        fact_ids_referenced=[],
        state_delta_suggestion={"trust": 0, "fear": 0, "guilt": 0, "sanity": 0},
    )
    assert len(resp.line.split()) == 35
