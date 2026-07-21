"""End-to-end mock playthrough test — reaches the ending in valid order.

Drives the pure rule engine (no Neo4j, no Ollama) and also exercises the
MockLLMService + validator to confirm dialogue lines stay in scope.
"""

from __future__ import annotations

import asyncio

from app.services import rules_engine as rx
from app.services.llm_service import MockLLMService, PromptContext, validate_llm_response
from app.services.rules_engine import (
    Action,
    GameState,
    Intent,
    apply_result,
    compute_reveal_scope,
    evaluate_action,
    evaluate_intent,
)


def _do_action(state: GameState, action: Action) -> None:
    result = evaluate_action(state, action)
    assert result.allowed, f"action {action} unexpectedly blocked: {result.reason}"
    apply_result(state, result)


def _do_intent(state: GameState, intent: Intent) -> None:
    result = evaluate_intent(state, intent)
    assert result.allowed, f"intent {intent} unexpectedly blocked: {result.reason}"
    apply_result(state, result)


def test_full_mock_playthrough_reaches_ending_in_order():
    state = GameState()

    # 1. Examine clock -> evidence + bell fact.
    _do_action(state, Action.EXAMINE_CLOCK)
    assert rx.EV_CLOCK in state.discovered_evidence
    assert rx.FACT_BELL_0217 in state.known_facts

    # 2. Examine ledger -> evidence + Elian fact.
    _do_action(state, Action.EXAMINE_LEDGER)
    assert rx.EV_LEDGER in state.discovered_evidence
    assert rx.FACT_ELIAN in state.known_facts

    # 3. Ask about 314 -> Mara admits she was awake.
    _do_intent(state, Intent.ASK_ROOM_314)
    assert rx.FACT_MARA_AWAKE in state.known_facts

    # 4. Confront -> figure revealed (identity remains unresolved).
    _do_intent(state, Intent.CONFRONT_MARA)
    assert rx.FACT_MARA_SAW_FIGURE in state.known_facts

    # 5. Request key -> key granted + corridor unlocked.
    _do_intent(state, Intent.REQUEST_KEY)
    assert state.has_key()
    assert state.corridor_unlocked is True

    # 6. Enter corridor.
    _do_action(state, Action.ENTER_CORRIDOR)
    assert state.location == rx.LOC_CORRIDOR

    # 7. Examine door -> ending.
    _do_action(state, Action.EXAMINE_DOOR)
    assert state.ended is True

    # The buried secret is never known.
    assert rx.FACT_MARA_ALLOWED_ENTRY not in state.known_facts


def test_ending_impossible_out_of_order():
    # Cannot examine the door first.
    state = GameState()
    assert evaluate_action(state, Action.EXAMINE_DOOR).allowed is False
    assert state.ended is False

    # Cannot get the key before confronting.
    assert evaluate_intent(state, Intent.REQUEST_KEY).allowed is False


def test_mock_dialogue_lines_stay_in_scope():
    """Every mock line must reference only allowed facts (validator passes)."""

    async def run() -> None:
        llm = MockLLMService()

        # Progress a state so several branches are unlocked.
        state = GameState()
        for action in (Action.EXAMINE_CLOCK, Action.EXAMINE_LEDGER):
            apply_result(state, evaluate_action(state, action))

        for intent in (
            Intent.ASK_ROOM_314,
            Intent.ASK_CLOCK,
            Intent.ASK_ELIAN,
            Intent.CONFRONT_MARA,
            Intent.SMALL_TALK,
            Intent.UNKNOWN,
        ):
            result = evaluate_intent(state, intent)
            allowed_ids, _ = compute_reveal_scope(state, intent, result)
            ctx = PromptContext(
                intent=intent.value,
                allowed_fact_ids=allowed_ids,
                allowed_suggested_intents=rx.allowed_suggested_intents(state, intent),
                has_clock=rx.EV_CLOCK in state.discovered_evidence,
                has_ledger=rx.EV_LEDGER in state.discovered_evidence,
                knows_saw_figure=rx.FACT_MARA_SAW_FIGURE in state.known_facts,
            )
            raw = await llm.generate(ctx)
            valid, resp, reason = validate_llm_response(raw, allowed_ids)
            assert valid, f"mock line out of scope for {intent}: {reason} / {raw}"
            assert resp is not None
            assert len(resp.line.split()) <= 35
            if result.allowed:
                apply_result(state, result)

    asyncio.run(run())


def test_mock_classifier_maps_portuguese_text():
    llm = MockLLMService()

    async def run() -> None:
        assert await llm.classify_intent("Quem entrou no quarto 314?") == Intent.ASK_ROOM_314.value
        assert await llm.classify_intent("Por que o relógio parou às 02:17?") == Intent.ASK_CLOCK.value
        assert await llm.classify_intent("Fale sobre Elian Voss.") == Intent.ASK_ELIAN.value
        assert await llm.classify_intent("Você está escondendo algo!") == Intent.CONFRONT_MARA.value
        assert await llm.classify_intent("Entregue a chave do corredor.") == Intent.REQUEST_KEY.value
        assert await llm.classify_intent("Olá, boa noite.") == Intent.SMALL_TALK.value
        assert await llm.classify_intent("asdfghjkl") == Intent.UNKNOWN.value

    asyncio.run(run())
