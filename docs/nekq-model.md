# O modelo NEKG — Narrative Epistemic Knowledge Graph

O NEKG estende o **Narrative Knowledge Graph** (usado no paper _"Guiding
Generative Storytelling with Knowledge Graphs"_) com uma **camada epistêmica**:
ele não representa apenas _o que é verdade_, mas também _quem sabe o quê_, _no que
acredita_, _o que esconde_ e _o que afirma_. Abaixo, cada conceito e seu papel
na PoC "O Quarto 314".

---

## Fact (Fato)

Uma proposição sobre o mundo. Na PoC, os fatos canônicos têm `canonical: true` e
um `spoiler_level` (1 = público, 5 = segredo profundo). Fatos **nunca** são
criados ou alterados pela LLM.

- Ex.: `bell_0217` — "O sino do farol tocou às 02:17." (spoiler 1)
- Ex.: `mara_allowed_entry` — "Mara não impediu a entrada da figura." (spoiler 5)

## Canonical truth (Verdade canônica)

O conjunto de fatos com `canonical: true` — **o que realmente aconteceu**. É
imutável durante o jogo e não pode ser apagada por ações normais. É a âncora
contra alucinação.

## Evidence (Evidência)

Um objeto ou observação que **apoia ou refuta** um fato, e que o jogador pode
**descobrir**. A descoberta é **por sessão**, via relação
`(:Player)-[:DISCOVERED]->(:Evidence)` — não existe flag global mutável.

- Ex.: `stopped_clock_0217` `-[:SUPPORTS]->` `bell_0217`.

## Knowledge (Conhecimento privado)

O que o NPC **sabe** sobre fatos canônicos, via `(:NPC)-[:KNOWS]->(:Fact)` com
`certainty` e `reveal_policy`. **Saber não é revelar**: Mara sabe que estava
acordada, mas só admite sob a política certa (ex.: `if_evidence_clock`).

## Belief / Hypothesis (Crença / Interpretação)

O que o NPC **acredita ou suspeita**, via `(:NPC)-[:BELIEVES]->(:Hypothesis)`. É
**não-canônica** (`canonical: false`) e **pode estar errada**. Nunca é promovida
a verdade automaticamente.

- Ex.: `elian_identity_hypothesis` — "A figura pode estar ligada a Elian Voss."
  (certeza 0.40)

## Secret (Segredo / Ocultação)

O que o NPC **deliberadamente esconde**, via `(:NPC)-[:CONCEALS]->(:Fact)` com
`motive` e `reveal_policy`. O segredo máximo (`mara_allowed_entry`) tem política
`never` — nenhuma regra jamais o libera.

## Claim (Alegação)

O que o NPC **efetivamente disse** ao jogador, persistido como nó `Claim` com
`truth_status` ∈ {truth, lie, evasion, uncertain_memory}. Uma alegação pode
divergir da verdade — é aí que mora a mentira, a evasão e a memória incerta.

## Player knowledge (Conhecimento do jogador)

Os fatos e pistas que o jogador **de fato descobriu**, persistidos por sessão via
`(:Player)-[:KNOWS_FACT]->(:Fact)` e `(:Player)-[:DISCOVERED]->(:Evidence)`. O
jogo começa com **zero** fatos e **zero** pistas.

## Psychological state (Estado psicológico)

`trust`, `fear`, `guilt`, `sanity`, `occult_exposure` — por sessão. A **SLM
interpreta** esse estado em linguagem/subtexto; o **rule engine decide** as
consequências. A LLM sugere deltas, mas eles são **ignorados**.

---

## Tabela-resumo: verdade × epistemologia

| Conceito         | Pergunta que responde                         | Pode a LLM criar/mudar? |
| ---------------- | --------------------------------------------- | ----------------------- |
| Fact / Canonical | O que é verdade?                              | Não                     |
| Evidence         | O que apoia/refuta um fato?                   | Não                     |
| Knowledge        | O que o NPC sabe?                             | Não                     |
| Belief/Hypothesis| No que o NPC acredita (talvez errado)?        | Não                     |
| Secret           | O que o NPC esconde e por quê?                | Não                     |
| Claim            | O que o NPC disse (verdade, mentira, evasão)? | Só o **texto**, validado|
| Player knowledge | O que o jogador descobriu?                    | Não                     |
| Estado psicológico | Como o NPC se sente?                         | Só **interpreta**       |

---

## Rótulos e relações no Neo4j

**Labels:** `NPC`, `Player`, `Session`, `Location`, `Item`, `Evidence`, `Fact`,
`Event`, `Belief`, `Secret`, `Claim`, `Hypothesis`, `Rule`, `Trace`.

**Relações principais:**

```
(:NPC)-[:KNOWS {certainty, reveal_policy}]->(:Fact)
(:NPC)-[:CONCEALS {motive, reveal_policy}]->(:Fact)
(:NPC)-[:BELIEVES {certainty, source}]->(:Hypothesis)
(:NPC)-[:OBSERVED {confidence, memory_stability, sensory_detail}]->(:Event)
(:Evidence)-[:SUPPORTS {weight}]->(:Fact)
(:Player)-[:DISCOVERED]->(:Evidence)
(:Player)-[:KNOWS_FACT]->(:Fact)
(:NPC)-[:MADE_CLAIM]->(:Claim)
(:Claim)-[:ABOUT]->(:Fact)
(:Session)-[:HAS_PLAYER]->(:Player)
(:Session)-[:AT_LOCATION]->(:Location)
(:Session)-[:TRACE]->(:Trace)
```

Nós canônicos de mundo são **compartilhados** entre sessões; `Player`, `Session`,
descobertas e deltas psicológicos são **por sessão**.
