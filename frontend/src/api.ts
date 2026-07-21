// Thin typed API client. The frontend only talks to the FastAPI backend —
// never to Neo4j or Ollama directly. No secrets live here.

import type {
  ActionResponse,
  DebugResponse,
  DialogueResponse,
  GameStateResponse,
  HealthResponse,
} from "./types";

const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(
      0,
      "Não foi possível contatar o backend. Ele está rodando na porta 8000?"
    );
  }
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore parse errors */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  startSession: () =>
    request<GameStateResponse>("/api/session/start", { method: "POST" }),

  getState: (sessionId: string) =>
    request<GameStateResponse>(`/api/session/${sessionId}/state`),

  postAction: (sessionId: string, action: string) =>
    request<ActionResponse>(`/api/session/${sessionId}/action`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),

  postDialogue: (
    sessionId: string,
    payload: { intent?: string; text?: string }
  ) =>
    request<DialogueResponse>(`/api/session/${sessionId}/dialogue`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getDebug: (sessionId: string) =>
    request<DebugResponse>(`/api/session/${sessionId}/debug`),
};
