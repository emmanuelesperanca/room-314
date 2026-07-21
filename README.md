# O Quarto 314 — NEKG Proof of Concept

Uma micro-investigação noir/lovecraftiana, local e jogável na web, criada para
validar uma mecânica original: o **NEKG — Narrative Epistemic Knowledge Graph**.

> Este projeto é um _upgrade_ conceitual do artigo _"Guiding Generative
> Storytelling with Knowledge Graphs"_ (Pan et al., 2025). Onde o paper usa um
> **Narrative Knowledge Graph** (fatos + relações narrativas), o NEKG adiciona uma
> **camada epistêmica**: separa a verdade objetiva daquilo que um NPC **sabe**,
> **acredita**, **esconde** e **afirma**. O jogo é o termômetro de qualidade
> dessa nova abordagem, pensada para virar artigo.

---

## 1. O que a PoC prova

A demo dura de 3 a 5 minutos e demonstra seis propriedades:

1. **O grafo preserva fatos canônicos imutáveis.** A LLM nunca os altera.
2. **NPCs têm epistemologia.** Mara possui conhecimento, crença, memória falha,
   segredos e mentiras — tudo separado da verdade objetiva.
3. **Ações e evidências mudam o subgrafo recuperado** para cada diálogo.
4. **Uma SLM local gera linguagem e subtexto**, mas nunca cria fatos, pistas,
   itens ou mudanças de mundo.
5. **Um rule engine determinístico** valida toda alteração de estado antes de
   escrevê-la no Neo4j.
6. **Toda resposta importante tem trace auditável**: fatos usados, fatos ocultos,
   regra aplicada e intenção validada.

O segredo mais profundo de Mara — que ela **não impediu a entrada da figura**
(`mara_allowed_entry`) — **nunca** pode ser revelado por nenhuma regra. O painel
de debug prova isso a cada turno.

---

## 2. Arquitetura

```
                      ┌────────────────────────────────────────────────┐
                      │                  FRONTEND (React)              │
                      │  UI de investigação · chips · texto livre ·    │
                      │  diário · painel de rastreabilidade NEKG        │
                      └───────────────┬────────────────────────────────┘
                                      │ HTTP (JSON) — nunca fala com o banco
                                      ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                              BACKEND (FastAPI)                              │
   │                                                                            │
   │   ação/intenção do jogador                                                 │
   │        │                                                                   │
   │        ▼                                                                   │
   │   ┌─────────────┐   estado    ┌──────────────┐   subgrafo   ┌───────────┐  │
   │   │ RULE ENGINE │───────────▶│  Neo4j (NEKG) │────────────▶│ RETRIEVAL │  │
   │   │ (autoridade)│◀───────────│  verdade +    │             │ contextual│  │
   │   └─────────────┘   grava     │  epistemologia│             └─────┬─────┘  │
   │        │  só o engine escreve └──────────────┘                    │        │
   │        │                                                          ▼        │
   │        │                              ┌───────────────────────────────┐    │
   │        │                              │  LLM (Ollama SLM ou MOCK)     │    │
   │        │        linguagem ◀───────────│  só produz FALA + intenção    │    │
   │        │                              └───────────────┬───────────────┘    │
   │        ▼                                              ▼                    │
   │   ┌──────────────────────────┐        ┌──────────────────────────────┐    │
   │   │ VALIDAÇÃO (Pydantic +    │        │  fallback determinístico       │    │
   │   │ escopo de fatos, R8)     │───────▶│  se a saída for inválida       │    │
   │   └──────────┬───────────────┘        └──────────────────────────────┘    │
   │              ▼                                                              │
   │   Claim + Trace persistidos ─────────▶ resposta ao frontend               │
   └───────────────────────────────────────────────────────────────────────────┘

  Fluxo de autoridade:
  Player action → rule engine → Neo4j state → contextual retrieval →
  LLM language → validation → claim/trace persistence → frontend
```

Detalhes em [docs/architecture.md](docs/architecture.md) e
[docs/nekq-model.md](docs/nekq-model.md).

---

## 3. Stack

| Camada   | Tecnologia                                                        |
| -------- | ----------------------------------------------------------------- |
| Backend  | Python 3.12+, FastAPI, Uvicorn, Pydantic v2, Neo4j Driver, httpx  |
| Frontend | React, TypeScript, Vite, CSS puro (`src/styles.css`)              |
| Grafo    | Neo4j Desktop (Community/Enterprise dev), sem APOC                 |
| SLM      | Ollama local (`/api/chat`) ou `MOCK_LLM=true`                     |
| Testes   | pytest (sem Neo4j e sem Ollama)                                    |

Sem Unity/Godot/Twine, sem LangChain/LangGraph, sem GraphRAG da Microsoft, sem
embeddings/vector search, sem login/auth, sem banco relacional. A LLM **nunca**
gera Cypher e o frontend **nunca** fala direto com o Neo4j.

---

## 4. Pré-requisitos

- **Python 3.12+** (validado também em 3.14).
- **Node.js 18+** e npm.
- **Neo4j Desktop** instalado e um DBMS local rodando.
- **Ollama** (opcional) em `http://localhost:11434`. Sem ele, use `MOCK_LLM=true`.

---

## 5. Configuração de ambiente

Copie o exemplo e ajuste a senha do Neo4j (o `.env` é git-ignored):

```powershell
Copy-Item .env.example .env
notepad .env   # ajuste NEO4J_PASSWORD
```

Conteúdo relevante do `.env`:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=sua-senha-aqui
NEO4J_DATABASE=room314

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b
MOCK_LLM=true

CORS_ORIGINS=http://localhost:5173
```

> A senha do Neo4j fica **somente** no `.env` do backend. Nunca vai para o
> frontend nem para arquivos versionados.

---

## 6. Passo a passo (Windows PowerShell)

### 6.1 Neo4j Desktop e seed do grafo

1. Abra o **Neo4j Desktop**, crie/abra um **Local DBMS**, defina uma senha e
   clique em **Start**.
2. Abra o **Neo4j Browser** (botão _Open_).
3. (Opcional, recomendado) Crie o banco dedicado `room314`. No Browser, com o
   banco `system` selecionado:
   ```cypher
   CREATE DATABASE room314;
   :use room314
   ```
   > Se o seu Neo4j for **Community** (banco único), pule a criação e use o banco
   > padrão `neo4j`. Nesse caso, deixe `NEO4J_DATABASE=neo4j` no `.env`.
4. Cole e execute o conteúdo de [neo4j/constraints.cypher](neo4j/constraints.cypher).
5. Cole e execute o conteúdo de [neo4j/seed.cypher](neo4j/seed.cypher).
   O seed é idempotente (usa `MERGE`), então pode ser reexecutado sem problemas.
6. (Reset de desenvolvimento) Para limpar tudo, execute
   [neo4j/reset.cypher](neo4j/reset.cypher) e depois `constraints` + `seed` de novo.

### 6.2 Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API: <http://localhost:8000>
- Documentação Swagger: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

> O backend lê o `.env` da raiz do repositório (ou de `backend/.env`). Como o
> DBMS do Neo4j Desktop precisa estar rodando para criar sessões, verifique o
> `/health` (campo `neo4j: true`).

### 6.3 Frontend

Em outro terminal:

```powershell
cd frontend
npm install
npm run dev
```

- Jogo: <http://localhost:5173>

### 6.4 SLM: MOCK ou Ollama

- **Sem Ollama (recomendado para demo):** deixe `MOCK_LLM=true` no `.env`. Um
  `MockLLMService` determinístico responde por Mara. A demo é totalmente jogável.
- **Com Ollama:** garanta o modelo baixado, por exemplo:
  ```powershell
  ollama pull gemma4:e4b
  ```
  Depois ajuste o `.env`:
  ```
  MOCK_LLM=false
  OLLAMA_MODEL=gemma4:e4b
  ```
  Reinicie o backend. A resposta da LLM passa por validação Pydantic + escopo de
  fatos; se for inválida, o backend cai no fallback determinístico em português.

> **Mudar o modelo Ollama:** basta alterar `OLLAMA_MODEL` no `.env` (ex.:
> `llama3.1:8b`, `qwen2.5:7b`) e reiniciar o backend.

---

## 7. Testes

Os testes **não exigem Neo4j nem Ollama**:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

Cobrem: gate do relógio antes de falar do 314, confronto exigindo as duas
evidências, chave exigindo a figura revelada, final exigindo corredor + chave,
o fato de **nenhuma regra liberar `mara_allowed_entry`**, um playthrough completo
em ordem válida, e o **validador rejeitando** respostas da LLM que citam fatos
fora do escopo.

---

## 8. Como jogar (playthrough de referência)

1. **Examinar relógio** → descobre `stopped_clock_0217`, conhece `bell_0217`.
2. **Examinar livro de hóspedes** → descobre `guest_ledger_elian`, conhece
   `elian_voss_disappearance`.
3. Chip **"Quem entrou no quarto 314?"** → agora Mara admite estar acordada
   (`mara_awake_0217`). Antes do relógio, ela evade.
4. Chip **"Você está escondendo algo."** → com as duas evidências, Mara revela
   que **viu uma figura** entrar (`mara_saw_figure`). A identidade fica em aberto.
5. Chip **"Entregue a chave."** → Mara entrega `corridor_key` e libera o corredor.
6. **Subir ao corredor** → você vai para o `corridor`.
7. **Examinar a porta 314** → evento final `door_opens`. Overlay:
   _"A porta se abre sozinha. Ao longe, o sino toca uma vez."_

Abra **"Mostrar rastreabilidade NEKG"** a qualquer momento para ver o trace real.

---

## 9. Limitações conscientes

- Sem voz.
- Sem arte de terceiros (visual 100% CSS).
- Sem embeddings / busca vetorial.
- A LLM não gera fatos, pistas nem Cypher.
- Um único NPC (Mara).
- História curta (5 batidas) e um único desfecho.

---

## 10. Próximos passos

- Múltiplos NPCs com epistemologias distintas.
- Modelo de confiança e fofoca entre NPCs.
- Documentos e busca híbrida (mantendo a autoridade determinística).
- Telemetria de contradições e vazamento de spoilers.
- Integração com engines (ex.: Unity) usando o backend como serviço de narrativa.

---

## 11. O que exige ação manual sua

- Criar/iniciar o **DBMS no Neo4j Desktop** e definir a senha.
- Rodar `constraints.cypher` e `seed.cypher` no **Neo4j Browser** (a aplicação não
  cria o esquema automaticamente, por segurança).
- Ajustar `NEO4J_PASSWORD` (e `NEO4J_DATABASE`, se usar `room314`) no `.env`.
- (Opcional) `ollama pull` do modelo, se for rodar com `MOCK_LLM=false`.
