import type { ActionOption } from "../types";

interface Props {
  actions: ActionOption[];
  onAction: (action: string, label: string) => void;
  loadingAction: string | null;
  disabled: boolean;
}

export default function ActionPanel({
  actions,
  onAction,
  loadingAction,
  disabled,
}: Props) {
  return (
    <section className="panel action">
      <h3 className="panel__subtitle">Ações</h3>
      <div className="action__list">
        {actions.map((a) => {
          const busy = loadingAction === a.action;
          return (
            <div key={a.action} className="action__row">
              <button
                className="btn btn--action"
                disabled={disabled || !a.enabled || loadingAction !== null}
                onClick={() => onAction(a.action, a.label)}
              >
                {busy ? "…" : a.label}
              </button>
              {!a.enabled && a.reason && (
                <span className="action__reason">🔒 {a.reason}</span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
