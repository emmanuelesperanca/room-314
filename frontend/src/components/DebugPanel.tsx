import type { DebugResponse } from "../types";

interface Props {
  debug: DebugResponse | null;
  show: boolean;
  onToggle: () => void;
}

function DebugList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="debug__block">
      <span className="debug__label">{label}</span>
      {items.length === 0 ? (
        <span className="debug__value debug__value--empty">[vazio]</span>
      ) : (
        <ul className="debug__items">
          {items.map((it, i) => (
            <li key={i} className="debug__mono">
              {it}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function DebugPanel({ debug, show, onToggle }: Props) {
  return (
    <section className="panel debug">
      <button className="debug__toggle" onClick={onToggle}>
        {show
          ? "▾ Ocultar rastreabilidade NEKG"
          : "▸ Mostrar rastreabilidade NEKG"}
      </button>

      {show && (
        <div className="debug__body">
          <p className="debug__note">
            Painel de demonstração da PoC. Mostra o <em>trace</em> real vindo do
            backend: a autoridade é determinística (rule engine), a SLM só produz
            linguagem, e o segredo <code>mara_allowed_entry</code> permanece
            sempre oculto.
          </p>

          {!debug ? (
            <p className="debug__empty">
              Sem trace ainda. Faça uma ação ou uma pergunta.
            </p>
          ) : (
            <>
              <div className="debug__block">
                <span className="debug__label">Última regra aplicada</span>
                <span className="debug__value debug__mono">
                  {debug.last_rule ?? "—"}
                </span>
              </div>

              <DebugList
                label="Estado psicológico de Mara"
                items={Object.entries(debug.mara_state).map(
                  ([k, v]) => `${k}: ${v}`
                )}
              />
              <DebugList
                label="Fatos permitidos agora"
                items={debug.allowed_fact_ids}
              />
              <DebugList
                label="Fatos ocultos (inclui o segredo)"
                items={debug.forbidden_fact_ids}
              />
              <DebugList
                label="Evidências descobertas"
                items={debug.evidence_discovered}
              />
              <DebugList
                label="Conhecimento do jogador"
                items={debug.player_knowledge}
              />
              {debug.last_trace && (
                <DebugList
                  label="Último trace persistido"
                  items={Object.entries(debug.last_trace).map(
                    ([k, v]) => `${k}: ${JSON.stringify(v)}`
                  )}
                />
              )}
              <DebugList
                label="Resumo de relações (NEKG)"
                items={debug.relationship_summary}
              />
            </>
          )}
        </div>
      )}
    </section>
  );
}
