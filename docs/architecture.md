# Arquitetura e autoridade — O Quarto 314 (NEKG)

Este documento descreve o fluxo de autoridade da PoC e por que ele garante que a
SLM nunca corrompe a verdade da história.

## Princípio central

> **A LLM só produz linguagem. O rule engine é a única autoridade sobre o
> estado. O grafo é a única fonte de verdade.**

A SLM (Ollama ou o mock) pode escolher _como_ Mara fala e _qual_ movimento de
fala tentar, dentro de um conjunto pré-aprovado. Ela **não** pode criar fatos,
evidências, itens, locais, regras, sessões, relações de progresso — nem Cypher.

## Fluxo de uma jogada

```
Player action/intent
      │
      ▼
[1] RULE ENGINE  (rules_engine.py, puro, determinístico)
      │   decide se a ação/intenção é permitida e quais são os efeitos
      ▼
[2] NEO4J STATE  (neo4j_service.py)
      │   o engine — e só ele — persiste o novo estado por sessão
      ▼
[3] CONTEXTUAL RETRIEVAL  (get_dialogue_context)
      │   seleciona o subgrafo mínimo: fatos permitidos, fatos proibidos (só ids),
      │   segredos (id + política, sem statement), hipóteses (não-canônicas),
      │   intenções de fala permitidas e um trace de seleção
      ▼
[4] LLM LANGUAGE  (llm_service.py: Ollama ou Mock)
      │   gera JSON estruturado: line, emotion, suggested_intent, claim_type,
      │   fact_ids_referenced, state_delta_suggestion (ignorado)
      ▼
[5] VALIDATION  (validate_llm_response + Pydantic)
      │   rejeita se o schema falhar OU se citar fato fora de allowed_fact_ids
      │   OU se citar o segredo. state_delta_suggestion é sempre descartado.
      │   Inválido → fallback determinístico em português.
      ▼
[6] CLAIM + TRACE PERSISTENCE
      │   grava a Claim (com truth_status) e o Trace auditável no grafo
      ▼
[7] FRONTEND
          recebe estado atualizado, fala de Mara e trace
```

## Camadas de autoridade (mapeadas para as regras)

| Regra | Garantia |
| ----- | -------- |
| **R1/R2** | Só ações reconhecidas descobrem evidências e liberam fatos. |
| **R3** | O relógio é pré-requisito para Mara admitir que estava acordada. |
| **R4** | O confronto exige as duas evidências; revela a figura, não a identidade. |
| **R5** | A chave exige a figura revelada. |
| **R6** | A porta exige corredor + chave; dispara o final. |
| **R7** | Texto livre é classificado numa enum fechada; nunca vira ação livre. |
| **R8** | Só o rule engine escreve no Neo4j. A LLM só fornece linguagem validada. |

## Por que o segredo nunca vaza

`mara_allowed_entry` está em três barreiras independentes:

1. **Nenhuma regra** o coloca em `new_facts` (teste automatizado garante isso).
2. `compute_reveal_scope` sempre o adiciona a `forbidden_fact_ids` e nunca a
   `allowed_fact_ids`.
3. `validate_llm_response` rejeita qualquer resposta que o cite, e `apply_result`
   remove-o do conhecimento do jogador por precaução (defesa em profundidade).

## Fronteiras de segurança

- **Injeção de Cypher:** todas as queries são fixas e parametrizadas; texto do
  usuário nunca é concatenado em Cypher.
- **Segredos:** a senha do Neo4j vive só no `.env` do backend (git-ignored). O
  frontend fala apenas com o backend via HTTP.
- **Prompt hardening:** ao enviar contexto para a LLM, fatos proibidos vão apenas
  como **ids** (sem o texto do segredo), com instrução explícita de não revelá-los.
