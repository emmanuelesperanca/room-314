"""Pydantic v2 models: LLM contract, API requests, and API responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------- #
# LLM structured-output contract
# --------------------------------------------------------------------------- #

EmotionLiteral = Literal["guarded", "fearful", "guilty", "evasive", "relieved", "shocked"]
SuggestedIntentLiteral = Literal[
    "evade", "deny", "reveal_awake", "reveal_figure", "offer_key", "small_talk"
]
ClaimTypeLiteral = Literal["truth", "lie", "evasion", "uncertain_memory"]


class StateDeltaSuggestion(BaseModel):
    """LLM's *suggested* deltas. Deliberately IGNORED by the backend.

    The rule engine is the only source of state changes (Rule R8).
    """

    trust: int = 0
    fear: int = 0
    guilt: int = 0
    sanity: int = 0


class LLMResponse(BaseModel):
    """The exact JSON contract Mara's model must return."""

    line: str
    emotion: EmotionLiteral
    suggested_intent: SuggestedIntentLiteral
    claim_type: ClaimTypeLiteral
    fact_ids_referenced: list[str] = Field(default_factory=list)
    state_delta_suggestion: StateDeltaSuggestion = Field(default_factory=StateDeltaSuggestion)

    @field_validator("line")
    @classmethod
    def _enforce_word_limit(cls, value: str) -> str:
        words = value.strip().split()
        if len(words) > 35:
            return " ".join(words[:35])
        return value.strip()


# --------------------------------------------------------------------------- #
# JSON Schema for Ollama structured output
# --------------------------------------------------------------------------- #

LLM_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "line": {"type": "string"},
        "emotion": {
            "type": "string",
            "enum": ["guarded", "fearful", "guilty", "evasive", "relieved", "shocked"],
        },
        "suggested_intent": {
            "type": "string",
            "enum": ["evade", "deny", "reveal_awake", "reveal_figure", "offer_key", "small_talk"],
        },
        "claim_type": {
            "type": "string",
            "enum": ["truth", "lie", "evasion", "uncertain_memory"],
        },
        "fact_ids_referenced": {"type": "array", "items": {"type": "string"}},
        "state_delta_suggestion": {
            "type": "object",
            "properties": {
                "trust": {"type": "integer"},
                "fear": {"type": "integer"},
                "guilt": {"type": "integer"},
                "sanity": {"type": "integer"},
            },
            "required": ["trust", "fear", "guilt", "sanity"],
        },
    },
    "required": [
        "line",
        "emotion",
        "suggested_intent",
        "claim_type",
        "fact_ids_referenced",
        "state_delta_suggestion",
    ],
}


# --------------------------------------------------------------------------- #
# API request models
# --------------------------------------------------------------------------- #


class ActionRequest(BaseModel):
    action: Literal["examine_clock", "examine_ledger", "enter_corridor", "examine_door"]


class DialogueRequest(BaseModel):
    text: str | None = None
    intent: (
        Literal[
            "ask_room_314",
            "ask_clock",
            "ask_elian",
            "confront_mara",
            "request_key",
            "small_talk",
            "unknown",
        ]
        | None
    ) = None


# --------------------------------------------------------------------------- #
# API response models
# --------------------------------------------------------------------------- #


class MaraStateModel(BaseModel):
    trust: int
    fear: int
    guilt: int
    sanity: int
    occult_exposure: int


class EvidenceModel(BaseModel):
    id: str
    name: str
    description: str


class FactModel(BaseModel):
    id: str
    statement: str


class ActionOption(BaseModel):
    action: str
    label: str
    enabled: bool
    reason: str | None = None


class DialogueChip(BaseModel):
    intent: str
    label: str
    enabled: bool
    reason: str | None = None


class SceneModel(BaseModel):
    location: str
    name: str
    description: str


class MaraView(BaseModel):
    emotion: str = "guarded"
    last_line: str | None = None


class EndingModel(BaseModel):
    title: str
    lines: list[str]


class GameStateResponse(BaseModel):
    session_id: str
    player_id: str
    scene: SceneModel
    location_label: str
    actions: list[ActionOption]
    dialogue_chips: list[DialogueChip]
    mara: MaraView
    discovered_evidence: list[EvidenceModel]
    known_facts: list[FactModel]
    ended: bool
    ending: EndingModel | None = None


class TraceModel(BaseModel):
    rule_id: str | None
    intent: str | None = None
    action: str | None = None
    classified_from_text: bool = False
    facts_used: list[str] = Field(default_factory=list)
    facts_hidden: list[str] = Field(default_factory=list)
    allowed_intents: list[str] = Field(default_factory=list)
    claim_type: str | None = None
    reason: str = ""
    llm_source: str = "n/a"
    validation: str = "n/a"


class ActionResponse(BaseModel):
    session_id: str
    action: str
    allowed: bool
    message: str
    events: list[str] = Field(default_factory=list)
    state: GameStateResponse
    trace: TraceModel


class DialogueResponse(BaseModel):
    session_id: str
    intent: str
    mara_line: str
    emotion: str
    claim_type: str
    state: GameStateResponse
    trace: TraceModel


class RelationshipSummaryItem(BaseModel):
    text: str


class DebugResponse(BaseModel):
    session_id: str
    canonical_facts: list[dict]
    player_knowledge: list[str]
    evidence_discovered: list[str]
    mara_state: MaraStateModel
    allowed_fact_ids: list[str]
    forbidden_fact_ids: list[str]
    last_rule: str | None
    last_trace: dict | None
    relationship_summary: list[str]


class HealthResponse(BaseModel):
    status: str
    backend: bool
    neo4j: bool
    ollama: bool
    mock_llm: bool
    model: str
