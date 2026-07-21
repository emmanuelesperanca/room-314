"""Dependency wiring: process-wide service singletons.

Services are created at application startup (see main.lifespan) and injected
into routes. The Neo4j password stays server-side only.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.services.llm_service import BaseLLMService, MockLLMService, OllamaLLMService
from app.services.neo4j_service import Neo4jService

_neo4j: Neo4jService | None = None
_llm: BaseLLMService | None = None


def init_services() -> None:
    global _neo4j, _llm
    settings: Settings = get_settings()
    _neo4j = Neo4jService(settings)
    if settings.mock_llm:
        _llm = MockLLMService()
    else:
        _llm = OllamaLLMService(settings.ollama_base_url, settings.ollama_model)


async def shutdown_services() -> None:
    global _neo4j, _llm
    if _neo4j is not None:
        await _neo4j.close()
    if _llm is not None:
        await _llm.close()
    _neo4j = None
    _llm = None


def get_neo4j() -> Neo4jService:
    if _neo4j is None:  # pragma: no cover - guarded by lifespan
        raise RuntimeError("Neo4j service not initialized")
    return _neo4j


def get_llm() -> BaseLLMService:
    if _llm is None:  # pragma: no cover - guarded by lifespan
        raise RuntimeError("LLM service not initialized")
    return _llm
