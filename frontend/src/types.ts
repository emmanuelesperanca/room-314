// Types mirroring the backend Pydantic response models.

export interface EvidenceModel {
  id: string;
  name: string;
  description: string;
}

export interface FactModel {
  id: string;
  statement: string;
}

export interface ActionOption {
  action: string;
  label: string;
  enabled: boolean;
  reason?: string | null;
}

export interface DialogueChip {
  intent: string;
  label: string;
  enabled: boolean;
  reason?: string | null;
}

export interface SceneModel {
  location: string;
  name: string;
  description: string;
}

export interface MaraView {
  emotion: string;
  last_line: string | null;
}

export interface EndingModel {
  title: string;
  lines: string[];
}

export interface GameStateResponse {
  session_id: string;
  player_id: string;
  scene: SceneModel;
  location_label: string;
  actions: ActionOption[];
  dialogue_chips: DialogueChip[];
  mara: MaraView;
  discovered_evidence: EvidenceModel[];
  known_facts: FactModel[];
  ended: boolean;
  ending: EndingModel | null;
}

export interface TraceModel {
  rule_id: string | null;
  intent?: string | null;
  action?: string | null;
  classified_from_text: boolean;
  facts_used: string[];
  facts_hidden: string[];
  allowed_intents: string[];
  claim_type?: string | null;
  reason: string;
  llm_source: string;
  validation: string;
}

export interface ActionResponse {
  session_id: string;
  action: string;
  allowed: boolean;
  message: string;
  events: string[];
  state: GameStateResponse;
  trace: TraceModel;
}

export interface DialogueResponse {
  session_id: string;
  intent: string;
  mara_line: string;
  emotion: string;
  claim_type: string;
  state: GameStateResponse;
  trace: TraceModel;
}

export interface DebugResponse {
  session_id: string;
  canonical_facts: Array<{
    id: string;
    statement: string;
    canonical: boolean;
    spoiler_level: number;
  }>;
  player_knowledge: string[];
  evidence_discovered: string[];
  mara_state: {
    trust: number;
    fear: number;
    guilt: number;
    sanity: number;
    occult_exposure: number;
  };
  allowed_fact_ids: string[];
  forbidden_fact_ids: string[];
  last_rule: string | null;
  last_trace: Record<string, unknown> | null;
  relationship_summary: string[];
}

export interface HealthResponse {
  status: string;
  backend: boolean;
  neo4j: boolean;
  ollama: boolean;
  mock_llm: boolean;
  model: string;
}

// Local UI log entry (not sent to the backend).
export type Speaker = "player" | "mara" | "system" | "action";

export interface LogEntry {
  speaker: Speaker;
  text: string;
  meta?: string;
}
