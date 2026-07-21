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
# Action evaluation (world mechanics)
# --------------------------------------------------------------------------- #


def evaluate_action(state: GameState, action: Action) -> RuleResult:
    if action == Action.EXAMINE_CLOCK:
        # R1_EXAMINE_CLOCK
        if state.location != LOC_RECEPTION:
            return RuleResult(
                "R1_EXAMINE_CLOCK", False,
                "Você precisa estar na recepção para examinar o relógio.",
            )
        return RuleResult(
            "R1_EXAMINE_CLOCK", True,
            "Relógio examinado.",
            narration="O relógio de parede parou exatamente às 02:17.",
            state_delta={"guilt": 5, "fear": 2},
            new_evidence=[EV_CLOCK],
            new_facts=[FACT_BELL_0217],
        )

    if action == Action.EXAMINE_LEDGER:
        # R2_EXAMINE_LEDGER
        if state.location != LOC_RECEPTION:
            return RuleResult(
                "R2_EXAMINE_LEDGER", False,
                "Você precisa estar na recepção para folhear o livro de hóspedes.",
            )
        return RuleResult(
            "R2_EXAMINE_LEDGER", True,
            "Livro de hóspedes examinado.",
            narration='No livro, o nome "Elian Voss" aparece parcialmente apagado.',
            state_delta={"fear": 3},
            new_evidence=[EV_LEDGER],
            new_facts=[FACT_ELIAN],
        )

    if action == Action.ENTER_CORRIDOR:
        # Movement gate: requires the key handed over by Mara (R5).
        if not state.has_key() or not state.corridor_unlocked:
            return RuleResult(
                "ENTER_CORRIDOR", False,
                "O corredor está trancado. Você precisa da chave que Mara guarda.",
            )
        if state.location == LOC_CORRIDOR:
            return RuleResult("ENTER_CORRIDOR", False, "Você já está no corredor.")
        return RuleResult(
            "ENTER_CORRIDOR", True,
            "Você sobe ao terceiro andar.",
            narration="A chave gira com dificuldade. O corredor se abre à sua frente.",
            set_location=LOC_CORRIDOR,
        )

    if action == Action.EXAMINE_DOOR:
        # R6_EXAMINE_DOOR — final beat.
        if state.location != LOC_CORRIDOR:
            return RuleResult(
                "R6_EXAMINE_DOOR", False,
                "A porta 314 fica no corredor. Você ainda não está lá.",
            )
        if not state.has_key():
            return RuleResult(
                "R6_EXAMINE_DOOR", False,
                "Você precisa da chave do corredor para chegar à porta.",
            )
        return RuleResult(
            "R6_EXAMINE_DOOR", True,
            "Você examina a porta do quarto 314.",
            narration="A porta se abre sozinha. Ao longe, o sino toca uma vez.",
            new_evidence=[EV_DOOR_MARK],
            events=["door_opens"],
        )

    return RuleResult("UNKNOWN_ACTION", False, "Ação desconhecida.")


# --------------------------------------------------------------------------- #
# Intent evaluation (dialogue mechanics)
# --------------------------------------------------------------------------- #


def evaluate_intent(state: GameState, intent: Intent) -> RuleResult:
    has_clock = EV_CLOCK in state.discovered_evidence
    has_ledger = EV_LEDGER in state.discovered_evidence
    knows_saw_figure = FACT_MARA_SAW_FIGURE in state.known_facts

    if intent == Intent.ASK_ROOM_314:
        # R3_ASK_314
        if not has_clock:
            return RuleResult(
                "R3_ASK_314", True,
                "Sem a prova do relógio, Mara evade sobre o quarto 314.",
                allowed_reveal_facts=[],
                forbidden_facts=[FACT_MARA_AWAKE, FACT_MARA_SAW_FIGURE, FACT_MARA_ALLOWED_ENTRY],
            )
        # With the clock, she may admit she was awake — but never the figure.
        return RuleResult(
            "R3_ASK_314", True,
            "Com o relógio, Mara pode admitir que estava acordada às 02:17.",
            new_facts=[FACT_MARA_AWAKE],
            allowed_reveal_facts=[FACT_BELL_0217, FACT_MARA_AWAKE],
            forbidden_facts=[FACT_MARA_SAW_FIGURE, FACT_FIGURE_LIGHT, FACT_MARA_ALLOWED_ENTRY],
        )

    if intent == Intent.ASK_CLOCK:
        if not has_clock:
            return RuleResult(
                "R3_ASK_314", True,
                "Mara desconversa sobre o relógio até que você o examine.",
                allowed_reveal_facts=[],
                forbidden_facts=[FACT_MARA_AWAKE, FACT_MARA_ALLOWED_ENTRY],
            )
        return RuleResult(
            "R3_ASK_314", True,
            "Mara reconhece a hora em que o relógio parou.",
            allowed_reveal_facts=[FACT_BELL_0217],
            forbidden_facts=[FACT_MARA_SAW_FIGURE, FACT_MARA_ALLOWED_ENTRY],
        )

    if intent == Intent.ASK_ELIAN:
        if not has_ledger:
            return RuleResult(
                "R2_EXAMINE_LEDGER", True,
                "Sem o livro de hóspedes, Mara nega conhecer o nome.",
                allowed_reveal_facts=[],
                forbidden_facts=[FACT_ELIAN, FACT_MARA_ALLOWED_ENTRY],
            )
        return RuleResult(
            "R2_EXAMINE_LEDGER", True,
            "Com o livro, Mara admite o desaparecimento de Elian Voss.",
            new_facts=[FACT_ELIAN],
            allowed_reveal_facts=[FACT_ELIAN],
            forbidden_facts=[FACT_MARA_SAW_FIGURE, FACT_MARA_ALLOWED_ENTRY],
        )

    if intent == Intent.CONFRONT_MARA:
        # R4_CONFRONT_MARA — requires BOTH evidences.
        if not (has_clock and has_ledger):
            return RuleResult(
                "R4_CONFRONT_MARA", False,
                "Você ainda não tem provas suficientes. Encontre o relógio e o livro.",
                forbidden_facts=[FACT_MARA_SAW_FIGURE, FACT_MARA_ALLOWED_ENTRY],
            )
        return RuleResult(
            "R4_CONFRONT_MARA", True,
            "Confrontada com relógio e livro, Mara revela que viu uma figura entrar no 314.",
            new_facts=[FACT_MARA_SAW_FIGURE, FACT_FIGURE_LIGHT],
            state_delta={"trust": 15, "guilt": 8, "fear": 8},
            allowed_reveal_facts=[FACT_MARA_SAW_FIGURE, FACT_FIGURE_LIGHT, FACT_MARA_AWAKE],
            # The identity stays unresolved; the deepest secret stays buried.
            forbidden_facts=[FACT_MARA_ALLOWED_ENTRY],
        )

    if intent == Intent.REQUEST_KEY:
        # R5_REQUEST_KEY — requires the figure revelation.
        if not knows_saw_figure:
            return RuleResult(
                "R5_REQUEST_KEY", False,
                "Mara não confia em você o bastante para entregar a chave. Ainda não.",
                forbidden_facts=[FACT_MARA_ALLOWED_ENTRY],
            )
        if state.has_key():
            return RuleResult(
                "R5_REQUEST_KEY", False,
                "Você já tem a chave do corredor.",
            )
        return RuleResult(
            "R5_REQUEST_KEY", True,
            "Mara entrega a chave do corredor e libera o acesso.",
            state_delta={"trust": 10, "fear": 5},
            granted_items=[ITEM_KEY],
            unlocked_locations=[LOC_CORRIDOR],
            allowed_reveal_facts=[FACT_MARA_SAW_FIGURE],
            forbidden_facts=[FACT_MARA_ALLOWED_ENTRY],
        )

    if intent == Intent.SMALL_TALK:
        return RuleResult(
            "R7_FREE_TEXT", True,
            "Conversa casual. Nenhuma mudança de estado.",
            forbidden_facts=[FACT_MARA_ALLOWED_ENTRY],
        )

    # UNKNOWN — no state change; short evasion (R7).
    return RuleResult(
        "R7_FREE_TEXT", True,
        "Intenção não reconhecida. Mara responde com uma evasão curta.",
        forbidden_facts=[FACT_MARA_ALLOWED_ENTRY],
    )


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


def allowed_suggested_intents(state: GameState, intent: Intent) -> list[str]:
    """Which speech moves Mara may take this turn (LLM `suggested_intent` enum)."""

    has_clock = EV_CLOCK in state.discovered_evidence
    has_ledger = EV_LEDGER in state.discovered_evidence
    knows_saw_figure = FACT_MARA_SAW_FIGURE in state.known_facts

    if intent == Intent.ASK_ROOM_314:
        return [SUGGESTED_REVEAL_AWAKE, SUGGESTED_EVADE] if has_clock else [SUGGESTED_DENY, SUGGESTED_EVADE]
    if intent == Intent.ASK_CLOCK:
        return [SUGGESTED_REVEAL_AWAKE, SUGGESTED_EVADE] if has_clock else [SUGGESTED_EVADE, SUGGESTED_SMALL_TALK]
    if intent == Intent.ASK_ELIAN:
        return [SUGGESTED_EVADE, SUGGESTED_SMALL_TALK] if has_ledger else [SUGGESTED_DENY, SUGGESTED_EVADE]
    if intent == Intent.CONFRONT_MARA:
        return [SUGGESTED_REVEAL_FIGURE, SUGGESTED_EVADE] if (has_clock and has_ledger) else [SUGGESTED_DENY, SUGGESTED_EVADE]
    if intent == Intent.REQUEST_KEY:
        return [SUGGESTED_OFFER_KEY, SUGGESTED_EVADE] if knows_saw_figure else [SUGGESTED_DENY, SUGGESTED_EVADE]
    if intent == Intent.SMALL_TALK:
        return [SUGGESTED_SMALL_TALK, SUGGESTED_EVADE]
    return [SUGGESTED_EVADE]


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
