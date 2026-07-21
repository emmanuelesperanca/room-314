"""FastAPI routes for Room 314."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.dependencies import get_llm, get_neo4j
from app.models import (
    ActionRequest,
    ActionResponse,
    DebugResponse,
    DialogueRequest,
    DialogueResponse,
    GameStateResponse,
    HealthResponse,
    MaraStateModel,
)
from app.services import narrative_service
from app.services import rules_engine as rx
from app.services.llm_service import BaseLLMService
from app.services.neo4j_service import Neo4jService

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(
    neo4j: Neo4jService = Depends(get_neo4j),
    llm: BaseLLMService = Depends(get_llm),
) -> HealthResponse:
    settings = get_settings()
    neo4j_ok = await neo4j.verify()
    if settings.mock_llm:
        ollama_ok = False  # not used in mock mode
    else:
        ollama_ok = await llm.health()
    return HealthResponse(
        status="ok",
        backend=True,
        neo4j=neo4j_ok,
        ollama=ollama_ok,
        mock_llm=settings.mock_llm,
        model=settings.ollama_model,
    )


async def _require_session(neo4j: Neo4jService, sid: str) -> None:
    try:
        exists = await neo4j.session_exists(sid)
    except Exception as exc:  # Neo4j down / unreachable
        raise HTTPException(status_code=503, detail=f"Neo4j indisponível: {exc}") from exc
    if not exists:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.post("/api/session/start", response_model=GameStateResponse, tags=["session"])
async def start_session(neo4j: Neo4jService = Depends(get_neo4j)) -> GameStateResponse:
    try:
        sid, pid, state = await neo4j.start_session()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível iniciar a sessão. Verifique o Neo4j Desktop e se o "
                f"seed foi executado. Detalhe: {exc}"
            ),
        ) from exc
    return await narrative_service.build_state_response(neo4j, sid, pid, state)


@router.get("/api/session/{session_id}/state", response_model=GameStateResponse, tags=["session"])
async def get_state(
    session_id: str, neo4j: Neo4jService = Depends(get_neo4j)
) -> GameStateResponse:
    await _require_session(neo4j, session_id)
    player_id, state = await neo4j.get_game_state(session_id)
    return await narrative_service.build_state_response(neo4j, session_id, player_id, state)


@router.post("/api/session/{session_id}/action", response_model=ActionResponse, tags=["gameplay"])
async def post_action(
    session_id: str,
    body: ActionRequest,
    neo4j: Neo4jService = Depends(get_neo4j),
) -> ActionResponse:
    await _require_session(neo4j, session_id)
    return await narrative_service.handle_action(neo4j, session_id, body.action)


@router.post("/api/session/{session_id}/dialogue", response_model=DialogueResponse, tags=["gameplay"])
async def post_dialogue(
    session_id: str,
    body: DialogueRequest,
    neo4j: Neo4jService = Depends(get_neo4j),
    llm: BaseLLMService = Depends(get_llm),
) -> DialogueResponse:
    await _require_session(neo4j, session_id)
    return await narrative_service.handle_dialogue(neo4j, llm, session_id, body.text, body.intent)


@router.get("/api/session/{session_id}/debug", response_model=DebugResponse, tags=["debug"])
async def get_debug(
    session_id: str, neo4j: Neo4jService = Depends(get_neo4j)
) -> DebugResponse:
    await _require_session(neo4j, session_id)
    player_id, state = await neo4j.get_game_state(session_id)

    fact_cat = await neo4j.fact_catalog()
    canonical_facts = [
        {
            "id": fid,
            "statement": data.get("statement"),
            "canonical": data.get("canonical"),
            "spoiler_level": data.get("spoiler_level"),
        }
        for fid, data in sorted(fact_cat.items())
    ]

    # General reveal scope for the current state (no specific intent).
    known = set(state.known_facts)
    allowed_fact_ids = sorted(f for f in known if f != rx.FACT_MARA_ALLOWED_ENTRY)
    forbidden_fact_ids = sorted(
        set(rx.ALWAYS_FORBIDDEN) | {f for f in rx.SENSITIVE_FACTS if f not in known}
    )

    last_trace = await neo4j.get_last_trace(session_id)
    relationship_summary = await neo4j.get_relationship_summary(session_id)

    return DebugResponse(
        session_id=session_id,
        canonical_facts=canonical_facts,
        player_knowledge=sorted(known),
        evidence_discovered=sorted(state.discovered_evidence),
        mara_state=MaraStateModel(**state.mara),
        allowed_fact_ids=allowed_fact_ids,
        forbidden_fact_ids=forbidden_fact_ids,
        last_rule=state.last_rule,
        last_trace=last_trace,
        relationship_summary=relationship_summary,
    )
