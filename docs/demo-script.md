# Roteiro de demonstração — 90 segundos

Objetivo: mostrar, em 90s, que o NEKG separa **verdade**, **epistemologia** e
**linguagem**, e que a autoridade é sempre do rule engine. Mantenha o painel
**"Mostrar rastreabilidade NEKG"** aberto durante toda a demo.

| Tempo | Botão / Ação | O que mostrar no grafo / trace | Propriedade NEKG demonstrada |
| ----- | ------------ | ------------------------------ | ---------------------------- |
| 0–10s | (abertura) Abra o painel de debug | `forbidden_fact_ids` já contém `mara_allowed_entry`; diário vazio | **Segredo imutável** existe antes de qualquer fala |
| 10–20s | Chip **"Quem entrou no quarto 314?"** (sem examinar nada) | Trace: `rule_id=R3_ASK_314`, `facts_used=[]`; Mara **evade** | **Saber ≠ revelar**: sem evidência, sem revelação |
| 20–35s | **Examinar relógio** | Diário ganha `stopped_clock_0217`; `Player-[:DISCOVERED]->Evidence`; guilt/fear sobem | **Evidência descoberta por sessão** muda o estado |
| 35–45s | **Examinar livro de hóspedes** | Diário ganha `guest_ledger_elian` e o fato `elian_voss_disappearance` | **Player knowledge** cresce; retrieval muda |
| 45–58s | Chip **"Quem entrou no quarto 314?"** de novo | Agora `facts_used` inclui `mara_awake_0217`; Mara admite estar acordada | **Ações mudam o subgrafo recuperado** |
| 58–70s | Chip **"Você está escondendo algo."** | `rule_id=R4_CONFRONT_MARA`; libera `mara_saw_figure`; a **identidade não é resolvida** | **Crença vs. verdade**: revela a figura, não quem é |
| 70–80s | Chip **"Entregue a chave."** → **Subir ao corredor** | Item `corridor_key` concedido; `Session.location=corridor` | **Rule engine é a autoridade** (a fala não destrancou nada) |
| 80–90s | **Examinar a porta 314** | Evento `door_opens`; overlay do final; `forbidden_fact_ids` **ainda** tem `mara_allowed_entry` | **Segredo nunca vaza** + trace auditável |

## Frase de fechamento sugerida

> "Em nenhum momento a SLM criou um fato, uma pista ou mudou o mundo. Ela só deu
> voz a Mara, dentro de um escopo que o grafo autorizou. A verdade, a mentira e o
> segredo estão no NEKG — e o segredo mais profundo continuou enterrado, com prova
> auditável a cada turno."

## Dica para a versão com Ollama

Se rodar com `MOCK_LLM=false`, faça a mesma sequência: a fala de Mara varia em
estilo, mas o **trace**, os fatos permitidos/proibidos e o desfecho permanecem
idênticos — porque a linguagem é livre, mas a autoridade não é.
