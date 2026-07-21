import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { DebugResponse, GameStateResponse, LogEntry } from "./types";
import GameHeader from "./components/GameHeader";
import ScenePanel from "./components/ScenePanel";
import ActionPanel from "./components/ActionPanel";
import MaraPanel from "./components/MaraPanel";
import DialogueLog from "./components/DialogueLog";
import JournalPanel from "./components/JournalPanel";
import DebugPanel from "./components/DebugPanel";

const STORAGE_KEY = "room314_session";
const INTRO_LINE =
  "Mais um perdido pela tempestade. O que você quer, detetive? Fale logo — a noite não me deixa em paz.";

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Ocorreu um erro inesperado.";
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [game, setGame] = useState<GameStateResponse | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [maraLine, setMaraLine] = useState<string>(INTRO_LINE);
  const [maraEmotion, setMaraEmotion] = useState<string>("guarded");
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [freeText, setFreeText] = useState("");
  const [debug, setDebug] = useState<DebugResponse | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [mock, setMock] = useState<boolean | null>(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    void boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function boot() {
    setBooting(true);
    setError(null);
    try {
      const health = await api.health().catch(() => null);
      if (health) setMock(health.mock_llm);

      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        try {
          const state = await api.getState(stored);
          hydrate(state, false);
          setBooting(false);
          return;
        } catch {
          localStorage.removeItem(STORAGE_KEY);
        }
      }
      await newSession();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBooting(false);
    }
  }

  function hydrate(state: GameStateResponse, fresh: boolean) {
    setSessionId(state.session_id);
    localStorage.setItem(STORAGE_KEY, state.session_id);
    setGame(state);
    if (fresh) {
      setLog([{ speaker: "system", text: state.scene.description }]);
      setMaraLine(INTRO_LINE);
      setMaraEmotion("guarded");
    }
    void refreshDebug(state.session_id);
  }

  async function newSession() {
    const state = await api.startSession();
    hydrate(state, true);
  }

  async function refreshDebug(sid: string) {
    try {
      const d = await api.getDebug(sid);
      setDebug(d);
    } catch {
      /* debug is best-effort */
    }
  }

  function pushLog(entry: LogEntry) {
    setLog((prev) => [...prev, entry]);
  }

  async function doAction(action: string, label: string) {
    if (!sessionId || !game || game.ended) return;
    setLoadingAction(action);
    setError(null);
    pushLog({ speaker: "action", text: label });
    try {
      const res = await api.postAction(sessionId, action);
      setGame(res.state);
      if (res.message) pushLog({ speaker: "system", text: res.message });
      await refreshDebug(sessionId);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoadingAction(null);
    }
  }

  async function doDialogue(
    intent: string | undefined,
    text: string | undefined,
    label: string
  ) {
    if (!sessionId || !game || game.ended) return;
    setAsking(true);
    setError(null);
    pushLog({ speaker: "player", text: label });
    try {
      const res = await api.postDialogue(sessionId, { intent, text });
      setGame(res.state);
      setMaraLine(res.mara_line);
      setMaraEmotion(res.emotion);
      pushLog({
        speaker: "mara",
        text: res.mara_line,
        meta: `${res.intent} · ${res.claim_type}`,
      });
      await refreshDebug(sessionId);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setAsking(false);
    }
  }

  function onAsk() {
    const text = freeText.trim();
    if (!text) return;
    setFreeText("");
    void doDialogue(undefined, text, text);
  }

  async function restart() {
    localStorage.removeItem(STORAGE_KEY);
    setLog([]);
    setDebug(null);
    setError(null);
    setLoadingAction(null);
    setAsking(false);
    try {
      await newSession();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (booting) {
    return (
      <div className="boot">
        <p className="boot__text">Acendendo as velas da Pensão Vesper…</p>
      </div>
    );
  }

  if (!game) {
    return (
      <div className="boot">
        <p className="boot__text">Não foi possível iniciar a investigação.</p>
        {error && <p className="boot__error">{error}</p>}
        <button className="btn btn--restart" onClick={() => void boot()}>
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <GameHeader locationLabel={game.location_label} mock={mock} />

      {error && (
        <div className="error-banner" role="alert">
          <span>⚠ {error}</span>
          <button className="error-banner__close" onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      )}

      <div className="layout">
        <div className="column column--left">
          <ScenePanel scene={game.scene} />
          <ActionPanel
            actions={game.actions}
            onAction={doAction}
            loadingAction={loadingAction}
            disabled={game.ended}
          />
          <JournalPanel
            evidence={game.discovered_evidence}
            facts={game.known_facts}
          />
        </div>

        <div className="column column--mid">
          <MaraPanel
            emotion={maraEmotion}
            line={maraLine}
            chips={game.dialogue_chips}
            onChip={(intent, label) => void doDialogue(intent, undefined, label)}
            freeText={freeText}
            setFreeText={setFreeText}
            onAsk={onAsk}
            asking={asking}
            disabled={game.ended}
          />
          <DialogueLog entries={log} />
        </div>
      </div>

      <DebugPanel
        debug={debug}
        show={showDebug}
        onToggle={() => setShowDebug((s) => !s)}
      />

      {game.ended && game.ending && (
        <div className="ending" role="dialog" aria-modal="true">
          <div className="ending__card">
            <div className="ending__glow" aria-hidden="true" />
            <h2 className="ending__title">{game.ending.title}</h2>
            {game.ending.lines.map((line, i) => (
              <p key={i} className="ending__line">
                {line}
              </p>
            ))}
            <button className="btn btn--restart" onClick={() => void restart()}>
              Recomeçar investigação
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
