"""LLM layer: deterministic validator + MockLLMService + OllamaLLMService.

Authority boundary (Rule R8): the LLM only produces language and *suggests* a
speech move constrained to an allow-list. It can never create facts, evidence,
items, locations, rules, sessions, progress relationships — or Cypher.

Every response passes through :func:`validate_llm_response`, which enforces the
Pydantic contract and the reveal scope before any persistence happens.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.models import LLM_JSON_SCHEMA, LLMResponse
from app.services import rules_engine as rx

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "mara_system_prompt.txt"


@dataclass
class PromptContext:
    """Everything the language layer is allowed to see for one dialogue turn."""

    intent: str
    allowed_facts: list[dict] = field(default_factory=list)  # {id, statement}
    allowed_fact_ids: list[str] = field(default_factory=list)
    forbidden_fact_ids: list[str] = field(default_factory=list)
    allowed_suggested_intents: list[str] = field(default_factory=list)
    mara_state: dict[str, int] = field(default_factory=dict)
    emotion_hint: str = "guarded"
    # decision flags (mock uses these; Ollama ignores them)
    has_clock: bool = False
    has_ledger: bool = False
    knows_saw_figure: bool = False
    rule_allowed: bool = True


# --------------------------------------------------------------------------- #
# Validation — the single gate every LLM/mock response must pass
# --------------------------------------------------------------------------- #


def validate_llm_response(
    raw: dict, allowed_fact_ids: list[str]
) -> tuple[bool, LLMResponse | None, str]:
    """Validate a raw LLM payload against the contract and the reveal scope.

    Returns ``(is_valid, response_or_none, reason)``. A response is rejected if:
      * it violates the Pydantic schema, or
      * it references any fact id outside ``allowed_fact_ids`` (Rule R8).

    ``state_delta_suggestion`` is accepted syntactically but always ignored by
    the caller — the rule engine owns state.
    """

    try:
        response = LLMResponse.model_validate(raw)
    except Exception:  # pydantic.ValidationError and malformed input
        return False, None, "schema_invalid"

    allowed = set(allowed_fact_ids)
    referenced = set(response.fact_ids_referenced)
    if not referenced.issubset(allowed):
        return False, None, "fact_out_of_scope"

    # The buried secret can never be referenced, even if somehow allow-listed.
    if rx.FACT_MARA_ALLOWED_ENTRY in referenced:
        return False, None, "forbidden_fact_referenced"

    return True, response, "ok"


# --------------------------------------------------------------------------- #
# Base interface
# --------------------------------------------------------------------------- #


class BaseLLMService:
    source: str = "base"

    async def classify_intent(self, text: str) -> str:  # pragma: no cover
        raise NotImplementedError

    async def generate(self, ctx: PromptContext) -> dict:  # pragma: no cover
        raise NotImplementedError

    async def health(self) -> bool:  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover
        return None


# --------------------------------------------------------------------------- #
# Portuguese keyword classifier (shared; Rule R7 MOCK path)
# --------------------------------------------------------------------------- #


def classify_text_heuristic(text: str | None) -> str:
    """Map free text onto the closed intent enum using PT-BR keywords."""

    if not text:
        return rx.Intent.UNKNOWN.value
    t = text.lower()

    def has(*words: str) -> bool:
        return any(w in t for w in words)

    if has("chave", "corredor", "me dê", "me de", "entregue", "acesso", "abrir o corredor"):
        return rx.Intent.REQUEST_KEY.value
    if has("esconde", "escondendo", "mentindo", "mente", "mentira", "verdade", "confesse", "sei que", "confront"):
        return rx.Intent.CONFRONT_MARA.value
    if has("elian", "voss", "livro", "hóspede", "hospede", "desapareceu", "desaparec"):
        return rx.Intent.ASK_ELIAN.value
    if has("relógio", "relogio", "02:17", "0217", "2:17", "sino", "que horas", "hora"):
        return rx.Intent.ASK_CLOCK.value
    if has("314", "quarto", "figura", "quem entrou", "porta", "trezentos e quatorze"):
        return rx.Intent.ASK_ROOM_314.value
    if has("olá", "ola", "oi", "boa noite", "tudo bem", "como vai", "tempestade", "obrigado", "obrigada"):
        return rx.Intent.SMALL_TALK.value
    return rx.Intent.UNKNOWN.value


# --------------------------------------------------------------------------- #
# Mock LLM — deterministic, no Ollama required
# --------------------------------------------------------------------------- #


class MockLLMService(BaseLLMService):
    source = "mock"

    async def health(self) -> bool:
        return True

    async def classify_intent(self, text: str) -> str:
        return classify_text_heuristic(text)

    async def generate(self, ctx: PromptContext) -> dict:
        intent = ctx.intent

        if intent == rx.Intent.ASK_ROOM_314.value:
            if ctx.has_clock:
                return _mk(
                    "Sim... eu estava acordada quando o sino tocou às 02:17. A recepção nunca dorme numa tempestade.",
                    "guarded", "reveal_awake", "uncertain_memory",
                    [rx.FACT_MARA_AWAKE, rx.FACT_BELL_0217], ctx,
                )
            return _mk(
                "O quarto 314 está fechado há anos. Não há nada lá. Por favor, não insista nesse assunto.",
                "evasive", "deny", "evasion", [], ctx,
            )

        if intent == rx.Intent.ASK_CLOCK.value:
            if ctx.has_clock:
                return _mk(
                    "Aquele relógio parou às 02:17. Foi quando o sino do farol tocou. Eu me lembro bem demais.",
                    "guilty", "reveal_awake", "truth", [rx.FACT_BELL_0217], ctx,
                )
            return _mk(
                "O relógio? Está parado há tempos. Nunca prestei atenção nele.",
                "evasive", "evade", "evasion", [], ctx,
            )

        if intent == rx.Intent.ASK_ELIAN.value:
            if ctx.has_ledger:
                return _mk(
                    "Elian Voss... desapareceu há dez anos. O nome dele ainda mancha o meu livro. Não gosto de lembrar.",
                    "fearful", "evade", "uncertain_memory", [rx.FACT_ELIAN], ctx,
                )
            return _mk(
                "Não conheço ninguém com esse nome. Muita gente passa por aqui, detetive.",
                "evasive", "deny", "lie", [], ctx,
            )

        if intent == rx.Intent.CONFRONT_MARA.value:
            if ctx.has_clock and ctx.has_ledger:
                return _mk(
                    "Está bem... eu vi. Uma figura entrou no 314 naquela noite, envolta numa luz esverdeada. Não pude fazer nada.",
                    "guilty", "reveal_figure", "truth",
                    [rx.FACT_MARA_SAW_FIGURE, rx.FACT_FIGURE_LIGHT], ctx,
                )
            return _mk(
                "Provas? Você tem só suspeitas. Volte quando souber do que está falando.",
                "guarded", "deny", "evasion", [], ctx,
            )

        if intent == rx.Intent.REQUEST_KEY.value:
            if ctx.knows_saw_figure:
                return _mk(
                    "Pegue a chave do corredor. Que Deus perdoe nós dois. Não abra o que não puder fechar.",
                    "fearful", "offer_key", "truth", [], ctx,
                )
            return _mk(
                "A chave? Não. Aquele corredor não é lugar para você. Ainda não.",
                "guarded", "deny", "evasion", [], ctx,
            )

        if intent == rx.Intent.SMALL_TALK.value:
            return _mk(
                "A tempestade não dá trégua. Fique perto do balcão, detetive. A noite ainda é longa.",
                "guarded", "small_talk", "truth", [], ctx,
            )

        # UNKNOWN
        return _mk(
            "Não entendi o que você quer. Seja direto, por favor.",
            "evasive", "evade", "evasion", [], ctx,
        )


def _mk(
    line: str,
    emotion: str,
    suggested_intent: str,
    claim_type: str,
    fact_ids: list[str],
    ctx: PromptContext,
) -> dict:
    """Build a mock payload, filtering facts to the allowed scope for safety."""

    safe_facts = [f for f in fact_ids if f in set(ctx.allowed_fact_ids)]
    # Keep suggested_intent inside the allowed move set when possible.
    move = suggested_intent
    if ctx.allowed_suggested_intents and move not in ctx.allowed_suggested_intents:
        move = ctx.allowed_suggested_intents[0]
    return {
        "line": line,
        "emotion": emotion,
        "suggested_intent": move,
        "claim_type": claim_type,
        "fact_ids_referenced": safe_facts,
        "state_delta_suggestion": {"trust": 0, "fear": 0, "guilt": 0, "sanity": 0},
    }


# --------------------------------------------------------------------------- #
# Ollama LLM — HTTP /api/chat with structured output
# --------------------------------------------------------------------------- #


class OllamaLLMService(BaseLLMService):
    source = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=60.0)
        self._system_template = _PROMPT_PATH.read_text(encoding="utf-8")

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            resp = await self._client.get("/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def classify_intent(self, text: str) -> str:
        """Ask Ollama to map free text onto the closed enum (JSON only)."""

        allowed = [i.value for i in rx.Intent]
        schema = {
            "type": "object",
            "properties": {"intent": {"type": "string", "enum": allowed}},
            "required": ["intent"],
        }
        system = (
            "Você classifica a fala de um jogador em UMA intenção. "
            "Responda somente JSON no formato {\"intent\": \"...\"} usando exatamente um destes valores: "
            + ", ".join(allowed)
            + "."
        )
        try:
            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text or ""},
                ],
                "format": schema,
                "stream": False,
                "options": {"temperature": 0.0},
            }
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            data = json.loads(content)
            intent = str(data.get("intent", "")).strip()
            if intent in allowed:
                return intent
        except Exception:
            pass
        return classify_text_heuristic(text)

    async def generate(self, ctx: PromptContext) -> dict:
        system = self._render_system(ctx)
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": _user_turn(ctx)},
            ],
            "format": LLM_JSON_SCHEMA,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return json.loads(content)

    def _render_system(self, ctx: PromptContext) -> str:
        allowed_lines = (
            "\n".join(f"- {f['id']}: {f['statement']}" for f in ctx.allowed_facts)
            or "- (nenhum fato liberado agora)"
        )
        forbidden = ", ".join(ctx.forbidden_fact_ids) or "(nenhum)"
        allowed_intents = ", ".join(ctx.allowed_suggested_intents) or "evade"
        state = ", ".join(f"{k}={v}" for k, v in ctx.mara_state.items())
        return (
            self._system_template.replace("{mara_state}", state)
            .replace("{intent}", ctx.intent)
            .replace("{emotion_hint}", ctx.emotion_hint)
            .replace("{allowed_facts}", allowed_lines)
            .replace("{forbidden_fact_ids}", forbidden)
            .replace("{allowed_intents}", allowed_intents)
        )


def _user_turn(ctx: PromptContext) -> str:
    return f"Intenção do jogador: {ctx.intent}. Responda como Mara, apenas com o JSON."
