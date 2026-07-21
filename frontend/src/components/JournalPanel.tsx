import type { EvidenceModel, FactModel } from "../types";

interface Props {
  evidence: EvidenceModel[];
  facts: FactModel[];
}

export default function JournalPanel({ evidence, facts }: Props) {
  return (
    <section className="panel journal">
      <h3 className="panel__subtitle">Diário</h3>

      <div className="journal__section">
        <h4 className="journal__heading">Evidências</h4>
        {evidence.length === 0 ? (
          <p className="journal__empty">Nenhuma evidência ainda.</p>
        ) : (
          <ul className="journal__list">
            {evidence.map((e) => (
              <li key={e.id} className="journal__item">
                <span className="journal__item-name">{e.name}</span>
                <span className="journal__item-desc">{e.description}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="journal__section">
        <h4 className="journal__heading">Fatos conhecidos</h4>
        {facts.length === 0 ? (
          <p className="journal__empty">Você ainda não sabe de nada.</p>
        ) : (
          <ul className="journal__list">
            {facts.map((f) => (
              <li key={f.id} className="journal__item">
                <span className="journal__item-desc">{f.statement}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
