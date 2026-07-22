"""Deterministic NEKG rule engine (pure Python, no Neo4j / no LLM).

This module is the single source of authority for state changes (Rule R8).
It operates on an in-memory :class:`GameState` and returns a :class:`RuleResult`
describing the deterministic consequences of an action or a dialogue intent.

The LLM never runs any of this logic and can never mutate state. It only
produces language, constrained by the reveal scope computed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services.case_loader import CaseDefinition, Rule, load_case
from app.services.conditions import StateView, evaluate_condition

# --------------------------------------------------------------------------- #
# Canonical identifiers (must match neo4j/seed.cypher)
# --------------------------------------------------------------------------- #

# Facts
FACT_BELL_0217 = "bell_0217"
FACT_MARA_AWAKE = "mara_awake_0217"
FACT_MARA_SAW_FIGURE = "mara_saw_figure"
FACT_DOOR_SEALED = "door_was_sealed"
FACT_FIGURE_LIGHT = "figure_blue_green_light"
FACT_MARA_ALLOWED_ENTRY = "mara_allowed_entry"  # SECRET — never released
FACT_ELIAN = "elian_voss_disappearance"

# Event
EVENT_ENTRY_314 = "entry_314_0217"

# Hypothesis (non-canonical)
HYPOTHESIS_ELIAN = "elian_identity_hypothesis"

# Evidence
EV_CLOCK = "stopped_clock_0217"
EV_LEDGER = "guest_ledger_elian"
EV_DOOR_MARK = "door_314_mark"

# Item
ITEM_KEY = "corridor_key"

# Locations
LOC_RECEPTION = "reception"
LOC_CORRIDOR = "corridor"
LOC_ROOM_314 = "room_314"

# The buried secret is ALWAYS forbidden, regardless of progress.
ALWAYS_FORBIDDEN: tuple[str, ...] = (FACT_MARA_ALLOWED_ENTRY,)

# Sensitive facts that must be hidden until their rule unlocks them.
SENSITIVE_FACTS: tuple[str, ...] = (
    FACT_MARA_AWAKE,
    FACT_MARA_SAW_FIGURE,
    FACT_FIGURE_LIGHT,
    FACT_MARA_ALLOWED_ENTRY,
)


class Action(str, Enum):
    """World actions (mechanical, not spoken)."""

    EXAMINE_CLOCK = "examine_clock"
    EXAMINE_LEDGER = "examine_ledger"
    ENTER_CORRIDOR = "enter_corridor"
    EXAMINE_DOOR = "examine_door"


class Intent(str, Enum):
    """Closed set of dialogue intents (Rule R7). No free-form actions."""

    ASK_ROOM_314 = "ask_room_314"
    ASK_CLOCK = "ask_clock"
    ASK_ELIAN = "ask_elian"
    CONFRONT_MARA = "confront_mara"
    REQUEST_KEY = "request_key"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


# Suggested LLM speech intents (what tone/move Mara may take).
SUGGESTED_EVADE = "evade"
SUGGESTED_DENY = "deny"
SUGGESTED_REVEAL_AWAKE = "reveal_awake"
SUGGESTED_REVEAL_FIGURE = "reveal_figure"
SUGGESTED_OFFER_KEY = "offer_key"
SUGGESTED_SMALL_TALK = "small_talk"


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


@dataclass
class GameState:
    """In-memory mirror of a session's mutable state.

    The Neo4j service hydrates this from the graph and persists it back, but the
    engine itself is storage-agnostic and fully unit-testable.
    """

    session_id: str = "local"
    location: str = LOC_RECEPTION
    discovered_evidence: set[str] = field(default_factory=set)
    known_facts: set[str] = field(default_factory=set)
    inventory: set[str] = field(default_factory=set)
    corridor_unlocked: bool = False
    ended: bool = False
    last_rule: str | None = None
    mara: dict[str, int] = field(
        default_factory=lambda: {
            "trust": 35,
            "fear": 70,
            "guilt": 76,
            "sanity": 58,
            "occult_exposure": 64,
        }
    )

    def has_key(self) -> bool:
        return ITEM_KEY in self.inventory


@dataclass
class RuleResult:
    """Deterministic outcome of evaluating an action or intent."""

    rule_id: str
    allowed: bool
    reason: str
    narration: str = ""  # short deterministic system/UI message
    state_delta: dict[str, int] = field(default_factory=dict)
    new_evidence: list[str] = field(default_factory=list)
    new_facts: list[str] = field(default_factory=list)
    unlocked_locations: list[str] = field(default_factory=list)
    granted_items: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    set_location: str | None = None
    # Reveal scope for the LLM (facts Mara may reference on THIS turn).
    allowed_reveal_facts: list[str] = field(default_factory=list)
    forbidden_facts: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Data-driven evaluation (rule logic loaded from cases/<id>.yaml)
# --------------------------------------------------------------------------- #

# The world lives in Neo4j; the deterministic rule logic (gates, branches,
# effects, reveal scope) is authored as data in cases/room_314.yaml and loaded
# here. No rule is hardcoded in Python anymore — R8 authority is preserved.
_CASE: CaseDefinition = load_case("room_314")


def _outcome_to_result(outcome: dict) -> RuleResult:
    """Materialize an authored outcome dict into a :class:`RuleResult`."""

    return RuleResult(
        rule_id=outcome.get("rule_id", "UNKNOWN"),
        allowed=bool(outcome.get("allowed", False)),
        reason=outcome.get("reason", ""),
        narration=outcome.get("narration", ""),
        state_delta=dict(outcome.get("state_delta", {})),
        new_evidence=list(outcome.get("new_evidence", [])),
        new_facts=list(outcome.get("new_facts", [])),
        unlocked_locations=list(outcome.get("unlocked_locations", [])),
        granted_items=list(outcome.get("granted_items", [])),
        events=list(outcome.get("events", [])),
        set_location=outcome.get("set_location"),
        allowed_reveal_facts=list(outcome.get("allowed_reveal_facts", [])),
        forbidden_facts=list(outcome.get("forbidden_facts", [])),
    )


def _select_outcome(rule: Rule | None, state: GameState) -> dict | None:
    """Return the outcome of the first branch whose condition matches."""

    if rule is None:
        return None
    view = StateView(state)
    for branch in rule.branches:
        if evaluate_condition(branch.when, view):
            return branch.outcome
    return None


def evaluate_action(state: GameState, action: Action | str) -> RuleResult:
    trigger = action.value if isinstance(action, Action) else str(action)
    outcome = _select_outcome(_CASE.actions.get(trigger), state)
    if outcome is None:
        return RuleResult("UNKNOWN_ACTION", False, "Ação desconhecida.")
    return _outcome_to_result(outcome)


# --------------------------------------------------------------------------- #
# Intent evaluation (dialogue mechanics)
# --------------------------------------------------------------------------- #


def evaluate_intent(state: GameState, intent: Intent | str) -> RuleResult:
    trigger = intent.value if isinstance(intent, Intent) else str(intent)
    outcome = _select_outcome(_CASE.intents.get(trigger), state)
    if outcome is None:
        # Unrecognized intent → short evasion, no state change (R7).
        return RuleResult(
            "R7_FREE_TEXT", True,
            "Intenção não reconhecida. Mara responde com uma evasão curta.",
            forbidden_facts=[FACT_MARA_ALLOWED_ENTRY],
        )
    return _outcome_to_result(outcome)


# --------------------------------------------------------------------------- #
# Apply results to in-memory state
# --------------------------------------------------------------------------- #


def apply_result(state: GameState, result: RuleResult) -> None:
    """Mutate ``state`` according to an ALLOWED result. Idempotent for sets."""

    if not result.allowed:
        return

    for key, delta in result.state_delta.items():
        state.mara[key] = clamp(state.mara.get(key, 0) + delta)

    state.discovered_evidence.update(result.new_evidence)
    state.known_facts.update(result.new_facts)
    state.inventory.update(result.granted_items)

    for loc in result.unlocked_locations:
        if loc == LOC_CORRIDOR:
            state.corridor_unlocked = True

    if result.set_location is not None:
        state.location = result.set_location

    if "door_opens" in result.events:
        state.ended = True

    # Safety net: the deepest secret can never be marked as known.
    state.known_facts.discard(FACT_MARA_ALLOWED_ENTRY)

    state.last_rule = result.rule_id


# --------------------------------------------------------------------------- #
# Reveal scope for the LLM prompt
# --------------------------------------------------------------------------- #


def allowed_suggested_intents(state: GameState, intent: Intent | str) -> list[str]:
    """Which speech moves Mara may take this turn (LLM `suggested_intent` enum).

    Derived from the matched branch's authored ``suggested_intents``.
    """

    trigger = intent.value if isinstance(intent, Intent) else str(intent)
    outcome = _select_outcome(_CASE.intents.get(trigger), state)
    if not outcome:
        return [SUGGESTED_EVADE]
    return list(outcome.get("suggested_intents", [SUGGESTED_EVADE]))


def compute_reveal_scope(state: GameState, intent: Intent, result: RuleResult) -> tuple[list[str], list[str]]:
    """Return ``(allowed_fact_ids, forbidden_fact_ids)`` for the LLM prompt.

    Allowed = facts the player already knows + facts this rule reveals now.
    Forbidden = every sensitive fact not allowed this turn, plus the buried
    secret, which is ALWAYS forbidden.
    """

    allowed: set[str] = set(state.known_facts)
    allowed.update(result.allowed_reveal_facts)
    allowed.update(result.new_facts)
    allowed.discard(FACT_MARA_ALLOWED_ENTRY)  # never allowed

    forbidden: set[str] = set(ALWAYS_FORBIDDEN)
    for fact in SENSITIVE_FACTS:
        if fact not in allowed:
            forbidden.add(fact)
    forbidden.update(result.forbidden_facts)

    return sorted(allowed), sorted(forbidden)
