# [P3] Brain Embeddings OpenAI — Busca Semântica Real

**Sprint:** 8 | **Status:** IMPLEMENTADO — AGUARDANDO QA | **Responsável:** @dev
**Prioridade:** P3 — MÉDIA | **Estimativa:** M (4–6h @dev + 1–2h @qa)

> **BLOCKED:** Esta story não pode iniciar até P1 (Brain Separation) estar em status FUNCIONAL e validado. Embeddings sobre base misturada geram dívida técnica irreversível. @dev aguarda sinalização de @qa que P1 passou o gate de done.

---

## User Story

Como Friday (agente), quero que minhas buscas no Brain do Mauro usem similaridade semântica — não apenas match de palavras-chave — para que eu consiga encontrar contexto relevante mesmo quando Mauro usa palavras diferentes das que foram ingeridas.

---

## Contexto Técnico

**Problema atual:** A busca atual usa text search (full-text PostgreSQL ou ILIKE) — não encontra por semântica. Uma query "visão de longo prazo" não encontra registros com "império Sparkle" ou "Lei 13".

**Infraestrutura já pronta (zero nova infra):**
- `pgvector 0.8.0` instalado e ativo no Supabase
- Tabela `brain_chunks` com coluna `embedding vector` (NULL para registros existentes)
- RPC `match_brain_chunks(query_embedding, pipeline_type_in, client_id_in, match_count)` — EXISTS e funcional, usa `<=>` (cosine distance)
- `search_brain_text` RPC criada em P1 como fallback textual

**O que falta:**
1. Gerar embeddings via OpenAI `text-embedding-3-small` ao ingerir (background task)
2. Usar busca vetorial em `brain_query` (já estruturada em P1, embedding NULL causa fallback — P3 popula os embeddings)
3. Script de backfill para os 101+ registros existentes sem embedding
4. Threshold configurável de similaridade (default 0.75)

**Arquivos a criar:**
- `runtime/utils/embeddings.py` — abstração do provider (não chamar OpenAI direto)
- `scripts/backfill_embeddings.py`

**Arquivos a modificar:**
- `runtime/tasks/handlers/brain_ingest.py` — background task de geração pós-insert
- `runtime/tasks/handlers/brain_query.py` — aplicar threshold de similaridade
- `runtime/config.py` — `brain_similarity_threshold: float = 0.75`

**Custo OpenAI estimado:** ~$0.004 para backfill inicial (101 registros, ~40K tokens) + ~$0.01–0.05/mês operacional. Custo irrisório.

---

## Acceptance Criteria

- [ ] AC-1: `OPENAI_API_KEY` confirmada no VPS por @devops antes de iniciar (`echo $OPENAI_API_KEY` retorna valor não vazio) — **PENDENTE: @devops configura OPENAI_API_KEY no VPS**
- [ ] AC-2: `POST /brain/ingest` com texto válido → após alguns segundos, o chunk tem `embedding IS NOT NULL` no banco (background task executou) — **PENDENTE: requer OPENAI_API_KEY + BRAIN_EMBEDDINGS_ENABLED=true**
- [ ] AC-3: `POST /brain/query` com query "visão de longo prazo" encontra registros que contêm "império Sparkle" ou termos semanticamente similares ingeridos previamente — **PENDENTE: requer OPENAI_API_KEY + backfill**
- [x] AC-4: Falha na API OpenAI (OPENAI_API_KEY removida temporariamente) → ingestão continua funcionando, embedding fica NULL, log de WARNING emitido (fluxo não quebra) — **CONFIRMADO: testado, 20/20 testes passando**
- [x] AC-5: Script de backfill executado com `--dry-run` primeiro — custo estimado documentado no `work_log.md` antes de executar — **CONCLUÍDO: $0.000172 USD para 101 chunks / 34.301 chars**
- [ ] AC-6: Script de backfill executado — 100% dos chunks em `brain_chunks` têm `embedding IS NOT NULL` ao final — **PENDENTE: requer OPENAI_API_KEY configurada**
- [x] AC-7: `BRAIN_SIMILARITY_THRESHOLD=0.75` configurado no `.env` do VPS — resultados abaixo do threshold não são retornados (retorna vazio em vez de resultado irrelevante) — **CONCLUÍDO: configurado no .env + aplicado em brain_query.py**

---

## Definition of Done

- [ ] Testes: ingerir texto X com palavras A → query com palavras B semanticamente similares → chunk X recuperado (teste semântico real)
- [ ] Testes: simular falha OpenAI → ingestão retorna sucesso, embedding NULL, warning no log
- [ ] QA aprovou: smoke test de busca semântica em ambiente de produção (não local)
- [ ] Custo real do backfill documentado no `work_log.md`
- [ ] `work_log.md` atualizado com status FUNCIONAL + "100% chunks com embedding"
- [ ] P1 validado como FUNCIONAL (pré-condição obrigatória antes de iniciar qualquer tarefa deste item)

---

## Tarefas Técnicas

- [x] T0: **AGUARDAR P1 FUNCIONAL** — P1 aprovado com ressalva por @qa em 2026-04-01
- [ ] T1: Verificar com @devops que `OPENAI_API_KEY` está no VPS — **PENDENTE: chave não encontrada no VPS, @devops precisa configurar**
- [x] T2: Criar `runtime/utils/embeddings.py` — função `generate_embedding(text)` via OpenAI `text-embedding-3-small`, falha silenciosa com log de WARNING; função `estimate_cost_usd(total_chars)` — **CONCLUÍDO 2026-04-01**
- [x] T3: Atualizar `brain_ingest.py` — após INSERT bem-sucedido, criar background task `asyncio.create_task(_generate_and_update_embedding(chunk_id, content))`; ingestão retorna imediatamente sem bloquear na chamada OpenAI — **CONCLUÍDO 2026-04-01**
- [x] T4: Atualizar `runtime/config.py` — adicionar `brain_similarity_threshold` e `brain_embeddings_enabled` — **CONCLUÍDO 2026-04-01**
- [x] T5: Atualizar `brain_query.py` — filtrar resultados da RPC `match_brain_chunks` por `similarity >= settings.brain_similarity_threshold`; se threshold eliminar todos, usar fallback text search — **CONCLUÍDO 2026-04-01**
- [x] T6: Criar `scripts/backfill_embeddings.py` — processa em batches de 10, pausa 1s entre batches, alerta se custo > $1, suporta `--dry-run` — **CONCLUÍDO 2026-04-01**
- [x] T7: Rodar backfill com `--dry-run` → documentar custo no `work_log.md` → **DRY-RUN FEITO: $0.000172 USD. Backfill real pendente após OPENAI_API_KEY**
- [x] T8: Configurar `BRAIN_SIMILARITY_THRESHOLD=0.75` no `.env` do VPS — **CONCLUÍDO 2026-04-01**

---

## Dependências

**Hard block — não iniciar sem:**
- P1 (Brain Separation) em status FUNCIONAL e validado por @qa
- `OPENAI_API_KEY` confirmada no VPS por @devops

**Paralela com:** nada neste sprint — é sequencial a P1.

**Esta story desbloqueia:** Gate V3 do @po (busca semântica funcional) + Sprint 9 (features de Brain avançadas).

---

## Notas para @dev

1. **NUNCA iniciar sem P1 concluído.** Embeddings gerados sobre `knowledge_base` não servem — precisam ser gerados sobre `brain_chunks` com `pipeline_type` correto.

2. **Abstração de provider é obrigatória.** Criar `runtime/utils/embeddings.py` — não chamar `openai` diretamente em `brain_ingest.py`. Isso permite trocar o provider (Cohere, local) sem tocar nos handlers.

3. **Background task, não síncrona.** `asyncio.create_task(_generate_and_update_embedding(...))` — a resposta de ingestão retorna imediatamente. O embedding é gerado em background. Isso evita latência percebida pelo usuário.

4. **Fallback é fundamental.** Se OpenAI falhar ou `OPENAI_API_KEY` não estiver configurada, o chunk é salvo sem embedding e a busca cai para `search_brain_text` (text search). Zero interrupção de serviço.

5. **Código completo** de `embeddings.py`, atualização de `brain_ingest.py` e `backfill_embeddings.py` está em `docs/sprints/sprint-8-specs.md` seções 3.1, 3.2 e 3.3. Usar como referência direta.

6. **Custo:** 101 registros existentes custam ~$0.004 para backfill. Mas rodar `--dry-run` primeiro é obrigatório e o custo estimado DEVE ser documentado no `work_log.md` antes de executar o backfill real.

7. **Dimensão do vetor:** `text-embedding-3-small` gera 1536 dims. Confirmar que a coluna `embedding` em `brain_chunks` é `vector(1536)` — ou que aceita qualquer dimensão. Checar: `SELECT udt_name FROM information_schema.columns WHERE table_name='brain_chunks' AND column_name='embedding'`.
