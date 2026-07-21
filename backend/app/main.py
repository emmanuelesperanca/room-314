"""FastAPI application entrypoint for Room 314 (NEKG PoC).

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.dependencies import init_services, shutdown_services


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create service singletons (does not force a DB connection).
    init_services()
    yield
    # Shutdown: close driver and HTTP clients.
    await shutdown_services()


settings = get_settings()

app = FastAPI(
    title="O Quarto 314 — NEKG PoC",
    description=(
        "Narrative Epistemic Knowledge Graph proof of concept. The rule engine is "
        "the only authority over state; the LLM only produces language."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["system"])
async def root() -> dict:
    return {
        "name": "O Quarto 314",
        "docs": "/docs",
        "health": "/health",
    }
