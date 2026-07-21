import { useEffect, useRef } from "react";
import type { LogEntry } from "../types";

interface Props {
  entries: LogEntry[];
}

export default function DialogueLog({ entries }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <section className="panel log">
      <h3 className="panel__subtitle">Registro da investigação</h3>
      <div className="log__scroll">
        {entries.map((entry, i) => (
          <div key={i} className={`log__entry log__entry--${entry.speaker}`}>
            {entry.speaker === "mara" && <span className="log__who">Mara</span>}
            {entry.speaker === "player" && <span className="log__who">Você</span>}
            <span className="log__text">{entry.text}</span>
            {entry.meta && <span className="log__meta">{entry.meta}</span>}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </section>
  );
}
