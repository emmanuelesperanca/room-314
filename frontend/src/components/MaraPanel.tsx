import { useEffect, useRef, useState } from "react";
import type { DialogueChip } from "../types";

const EMOTION_LABELS: Record<string, string> = {
  guarded: "Cautelosa",
  fearful: "Assustada",
  guilty: "Culpada",
  evasive: "Evasiva",
  relieved: "Aliviada",
  shocked: "Chocada",
};

interface Props {
  emotion: string;
  line: string;
  chips: DialogueChip[];
  onChip: (intent: string, label: string) => void;
  freeText: string;
  setFreeText: (value: string) => void;
  onAsk: () => void;
  asking: boolean;
  disabled: boolean;
}

export default function MaraPanel({
  emotion,
  line,
  chips,
  onChip,
  freeText,
  setFreeText,
  onAsk,
  asking,
  disabled,
}: Props) {
  // Simple typewriter effect on the latest line.
  const [shown, setShown] = useState("");
  const indexRef = useRef(0);

  useEffect(() => {
    setShown("");
    indexRef.current = 0;
    const id = window.setInterval(() => {
      indexRef.current += 1;
      setShown(line.slice(0, indexRef.current));
      if (indexRef.current >= line.length) {
        window.clearInterval(id);
      }
    }, 18);
    return () => window.clearInterval(id);
  }, [line]);

  const emotionLabel = EMOTION_LABELS[emotion] ?? emotion;

  return (
    <section className="panel mara">
      <div className="mara__stage">
        <div className="mara__silhouette" aria-hidden="true" />
        <div className="mara__head">
          <span className="mara__name">Mara Doyle</span>
          <span className={`mara__emotion mara__emotion--${emotion}`}>
            {emotionLabel}
          </span>
        </div>
      </div>

      <p className="mara__line">
        <span className="mara__quote">“</span>
        {shown}
        <span className="tw-cursor" aria-hidden="true">
          ▍
        </span>
      </p>

      <div className="mara__chips">
        {chips.map((c) => (
          <button
            key={c.intent}
            className="chip"
            disabled={disabled || !c.enabled || asking}
            title={c.reason ?? undefined}
            onClick={() => onChip(c.intent, c.label)}
          >
            {c.label}
            {!c.enabled && <span className="chip__lock"> 🔒</span>}
          </button>
        ))}
      </div>

      <form
        className="mara__ask"
        onSubmit={(e) => {
          e.preventDefault();
          if (freeText.trim()) onAsk();
        }}
      >
        <input
          className="mara__input"
          type="text"
          placeholder="Fale com Mara..."
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          disabled={disabled || asking}
        />
        <button
          className="btn btn--ask"
          type="submit"
          disabled={disabled || asking || !freeText.trim()}
        >
          {asking ? "…" : "Perguntar"}
        </button>
      </form>
    </section>
  );
}
