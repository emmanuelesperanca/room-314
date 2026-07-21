import type { SceneModel } from "../types";

interface Props {
  scene: SceneModel;
}

export default function ScenePanel({ scene }: Props) {
  return (
    <section className="panel scene">
      <h2 className="panel__title">{scene.name}</h2>
      <p className="scene__text">{scene.description}</p>
    </section>
  );
}
