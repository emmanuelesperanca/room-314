interface Props {
  locationLabel: string;
  mock: boolean | null;
}

export default function GameHeader({ locationLabel, mock }: Props) {
  return (
    <header className="header">
      <div className="header__brand">
        <h1 className="header__title">O QUARTO 314</h1>
        <p className="header__subtitle">Pensão Vesper · Tempestade · 02:17</p>
      </div>
      <div className="header__right">
        {mock !== null && (
          <span className={`badge ${mock ? "badge--mock" : "badge--live"}`}>
            {mock ? "SLM: MOCK" : "SLM: Ollama"}
          </span>
        )}
        <div className="header__location">
          <span className="header__location-label">Local</span>
          <span className="header__location-value">{locationLabel}</span>
        </div>
      </div>
    </header>
  );
}
