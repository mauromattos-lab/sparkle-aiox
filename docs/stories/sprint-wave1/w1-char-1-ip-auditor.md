---
epic: EPIC-WAVE1
story: W1-CHAR-1
title: Personagens — IP Auditor com Lore Real da Zenya (Consistência de Conteúdo)
status: Ready for Dev
priority: Alta
executor: "@dev -> @devops -> @qa"
sprint: Wave 1 — Domain Activation (2026-04-07+)
depends_on:
  - W0-CHAR-1 (lore canônico ingerido no Brain — namespace sparkle-lore com 33+ chunks approved)
  - W0-BRAIN-2 (retrieval funcional — curadoria do backlog concluída)
unblocks:
  - W1-CONTENT-1 (conteúdo gerado com lore injetado passa pelo IP Auditor antes de aprovação)
estimated_effort: "4-6h (@dev 3-5h + @qa 1h)"
prd_reference: docs/prd/domain-personagens-ip-prd.md
architecture_reference: docs/architecture/domain-personagens-ip-architecture.md
---

# Story W1-CHAR-1 — IP Auditor: Validar Conteúdo Contra Lore Real da Zenya

## Story

**Como** pipeline de conteúdo da Sparkle,
**Quero** que o IP Auditor valide posts, scripts e carrosseis gerados contra o lore canônico real da Zenya armazenado no Brain (`namespace='sparkle-lore'`) e na tabela `character_lore`,
**Para que** nenhum conteúdo público da Zenya contradiga seu lore canônico aprovado por Mauro, e inconsistências de personagem sejam detectadas antes de ir para aprovação humana.

---

## Contexto Técnico

**Estado atual:**

O `ip_auditor.py` (`sparkle-runtime/runtime/content/ip_auditor.py`) já existe e está integrado ao pipeline. Ele roda entre `video_done` e `pending_approval` — **nunca bloqueia**, apenas registra warnings em `pipeline_log['ip_audit']`.

O problema atual é a base de lore que o auditor consulta. Com W0-CHAR-1 concluído:
- `sparkle-lore` tem 33 chunks `approved` com lore canônico real da Zenya
- `character_lore` tem 13 entries para `character_slug='zenya'`

Mas o auditor em produção ainda sofre de dois problemas técnicos descobertos no código:

**Problema 1 — Query RPC não filtra por namespace corretamente:**

Em `ip_auditor.py`, a função `_query_sparkle_lore()` chama `match_brain_chunks` via RPC e depois filtra manualmente no Python:

```python
lore_chunks = [
    c for c in chunks
    if (c.get("namespace") == "sparkle-lore"
        or (c.get("chunk_metadata") or {}).get("namespace") == "sparkle-lore"
        or "sparkle-lore" in str(c.get("source_url") or ""))
]
```

A RPC `match_brain_chunks` recebe `pipeline_type_in="especialista"` — este filtro não garante que apenas chunks de `sparkle-lore` sejam retornados. Com o Brain agora populado com lore real, a query precisa ser precisa: usar `namespace='sparkle-lore'` como filtro primário na RPC, não como pós-filtro Python.

**Problema 2 — Detecção de restrições depende de tags ausentes no lore:**

O lore canônico ingerido em W0-CHAR-1 usa `metadata.lore_type='canonical'` e `metadata.lore_type='bible'`. O auditor atual só detecta conflitos quando um chunk tem tag `restriction` ou `type='restriction'`. Lore canônico não tem essas tags — o auditor passa tudo como `lore_ok=True` sem realmente comparar o conteúdo gerado com o lore.

A solução: adicionar uma segunda modalidade de verificação — **comparação semântica positiva** (o conteúdo *respeita* o lore?) em vez de apenas filtro por tag de restrição (o conteúdo *viola* uma restrição explícita?).

**Problema 3 — `character_lore` não é consultada:**

O auditor atual consulta apenas o Brain. Com 13 entries em `character_lore`, é possível fazer uma checagem estruturada de consistência (arquétipo, tom de comunicação, backstory) sem depender exclusivamente de similaridade vetorial.

**Arquivos relevantes:**
```
sparkle-runtime/runtime/content/ip_auditor.py    ← auditor existente (modificar)
sparkle-runtime/runtime/content/pipeline.py      ← integração existente (sem mudança)
sparkle-runtime/runtime/characters/lore_loader.py ← padrão de consulta character_lore
sparkle-runtime/runtime/brain/                   ← namespace e embedding
```

---

## Critérios de Aceitação

### AC-1 — Query de lore precisa no Brain

- [ ] `_query_sparkle_lore()` usa filtro `namespace='sparkle-lore'` como parâmetro primário da RPC `match_brain_chunks` (não como pós-filtro Python)
- [ ] Se a RPC não aceitar namespace como parâmetro direto, a query usa `supabase.table("brain_chunks").select(...).eq("namespace", "sparkle-lore")` com filtro por embedding via `pgvector`
- [ ] `POST /brain/query` com `namespace='sparkle-lore'` retorna chunks relevantes de lore da Zenya para query "personalidade da Zenya"
- [ ] `POST /brain/query` retorna chunks relevantes para query "arquétipo narrativo Zenya"

### AC-2 — Verificação semântica positiva (lore compliance)

- [ ] Para cada peça auditada, o auditor executa uma query de lore com o tema + primeiros 200 chars do voice_script
- [ ] Auditor verifica se o conteúdo gerado é **compatível** com os top-3 chunks de lore retornados (não apenas se viola uma restrição explícita)
- [ ] Compatibilidade é verificada por um segundo prompt ao Claude Haiku: `"O texto abaixo é consistente com o lore da Zenya descrito? Responda COMPATIVEL ou INCOMPATIVEL com justificativa em até 20 palavras."`
- [ ] Resultado da verificação semântica é registrado em `pipeline_log['ip_audit']['lore_compliance']`
- [ ] Se Claude Haiku retorna `INCOMPATIVEL`, um warning é adicionado com a justificativa — **nunca bloqueia o pipeline**

### AC-3 — Consulta a character_lore

- [ ] Auditor consulta `character_lore` WHERE `character_slug='zenya'` AND `lore_type IN ('personality', 'backstory', 'arc')` AND `is_public=true`
- [ ] Entries retornadas são incluídas no contexto de lore enviado para verificação do Haiku (AC-2)
- [ ] Se `character_lore` retornar vazio, auditor continua com lore do Brain (graceful degradation)

### AC-4 — Resultado de auditoria enriquecido

- [ ] `audit_result` em `pipeline_log['ip_audit']` passa a incluir:
  ```json
  {
    "lore_ok": true|false,
    "lore_compliance": "COMPATIVEL|INCOMPATIVEL|SKIPPED",
    "lore_compliance_reason": "string ou null",
    "lore_chunks_used": 3,
    "character_lore_entries_used": 2,
    "repetition_ok": true|false,
    "warnings": [],
    "audited_at": "ISO"
  }
  ```
- [ ] Campo `lore_chunks_used` indica quantos chunks do Brain foram usados na verificação
- [ ] Campo `character_lore_entries_used` indica quantas entries de `character_lore` foram usadas

### AC-5 — Comportamento não-bloqueante mantido

- [ ] IP Auditor **nunca** impede o avanço de uma peça para `pending_approval` — apenas registra warnings
- [ ] Em caso de erro no Haiku (timeout, quota), auditor registra `"lore_compliance": "SKIPPED"` e avança
- [ ] Em caso de lore vazio no Brain (namespace não populado), auditor registra warning mas não falha

### AC-6 — Visibilidade no Portal

- [ ] Portal HQ exibe badge de auditoria em cada peça na fila de aprovação: `Lore OK`, `Lore: Warning` ou `Auditoria Skipped`
- [ ] Ao expandir uma peça na fila, os warnings de lore são exibidos para Mauro com o texto do chunk conflitante

### AC-7 — Testes automatizados

- [ ] `tests/content/test_ip_auditor.py` cobre: lore compatível (sem warnings), lore incompatível (warning gerado), erro do Haiku (SKIPPED), character_lore vazio (graceful degradation)
- [ ] `pytest tests/content/test_ip_auditor.py` passa no VPS

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] `audit_piece()` consultando Brain com namespace correto E `character_lore` da Zenya
- [ ] Pelo menos 1 peça de teste auditada com `lore_compliance='COMPATIVEL'` registrada no `pipeline_log`
- [ ] Pelo menos 1 peça de teste auditada com `lore_compliance='INCOMPATIVEL'` detectando inconsistência real
- [ ] Badge de auditoria visível no Portal HQ
- [ ] @qa validou auditoria com peça compatível e peça com inconsistência intencional
- [ ] @devops confirmou deploy no VPS sem regressão no pipeline existente
- [ ] Nenhum conteúdo bloqueado por erro do auditor — comportamento não-bloqueante verificado

---

## Tarefas Técnicas

- [ ] **T1 — Diagnóstico da query RPC atual:** Verificar `match_brain_chunks` — aceita parâmetro de namespace? Se sim, modificar a chamada. Se não, implementar query direta via `brain_chunks` table com filtro `namespace='sparkle-lore'` + similaridade vetorial.
- [ ] **T2 — Refatorar `_query_sparkle_lore()`:** Garantir que apenas chunks de `sparkle-lore` são retornados, sem pós-filtro Python frágil. Documentar a RPC usada no comentário da função.
- [ ] **T3 — Adicionar `_query_character_lore()`:** Nova função em `ip_auditor.py` que consulta `character_lore` para `character_slug='zenya'` com filtro de `lore_type` e `is_public=true`. Retorna lista de strings de conteúdo.
- [ ] **T4 — Implementar verificação semântica positiva via Haiku:**
  - Montar prompt com: conteúdo gerado (tema + voice_script + caption) + top-3 chunks de lore + entries de character_lore
  - Chamar Claude Haiku com timeout de 10s
  - Parsear resposta para `COMPATIVEL` | `INCOMPATIVEL`
  - Extrair justificativa (primeiros 100 chars após a palavra-chave)
- [ ] **T5 — Atualizar `audit_result` dict:** Adicionar campos `lore_compliance`, `lore_compliance_reason`, `lore_chunks_used`, `character_lore_entries_used`
- [ ] **T6 — Atualizar Portal HQ:** Adicionar badge de auditoria na listagem de peças pendentes de aprovação. Badge deve mostrar status da auditoria de forma visual sem poluir a UI.
- [ ] **T7 — Escrever testes em `tests/content/test_ip_auditor.py`:** Cobertura dos cenários do AC-7.
- [ ] **T8 — Smoke test em produção:** Gerar uma peça de teste (tema compatível com lore da Zenya) e verificar que `pipeline_log` contém `lore_compliance='COMPATIVEL'`. Gerar segunda peça com tema intencionalmente fora do arquétipo e verificar que warning é registrado.

---

## Dependências

**Esta story depende de:**
- W0-CHAR-1 (lore canônico da Zenya ingerido — `sparkle-lore` com 33+ chunks `approved`, `character_lore` com 13 entries) — **Done**
- W0-BRAIN-2 (curadoria do backlog concluída — retrieval retorna chunks relevantes) — **Done**

**Esta story desbloqueia:**
- W1-CONTENT-1 — Geração de conteúdo com lore injetado (o auditor precisa estar funcional antes de o pipeline de geração com lore entrar em produção)

**Referências de código existente:**
- `runtime/content/ip_auditor.py` — módulo a modificar (não reescrever)
- `runtime/characters/lore_loader.py` — padrão de consulta `character_lore` a reutilizar
- `runtime/content/pipeline.py` — integração com auditor (linha `await audit_piece(piece)` — não modificar)

---

## Pipeline AIOS

| Etapa | Agente | Entrega |
|-------|--------|---------|
| Diagnóstico T1 + T2 (query RPC) | @dev | `_query_sparkle_lore()` refatorada com namespace correto |
| T3 + T4 (character_lore + Haiku) | @dev | Verificação semântica positiva implementada |
| T5 (audit_result enriquecido) | @dev | Campos novos em `pipeline_log['ip_audit']` |
| T6 (Portal badge) | @dev | Badge de auditoria visível no HQ |
| T7 (testes) | @dev | `test_ip_auditor.py` passando |
| Deploy VPS | @devops | `ip_auditor.py` atualizado em produção |
| Smoke test + validação | @qa | Auditoria com peça compatível e com inconsistência verificadas |

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `sparkle-runtime/runtime/content/ip_auditor.py` | Modificar | Refatorar query de namespace, adicionar `_query_character_lore()`, implementar verificação Haiku, enriquecer `audit_result` |
| `sparkle-runtime/runtime/content/pipeline.py` | Não modificar | Integração existente com `audit_piece()` — sem mudança |
| `sparkle-runtime/runtime/characters/lore_loader.py` | Ler | Padrão de consulta `character_lore` a reutilizar em T3 |
| `portal/app/hq/content/` | Modificar | Adicionar badge de auditoria na fila de aprovação (AC-6) |
| `sparkle-runtime/tests/content/test_ip_auditor.py` | Criar | Testes automatizados dos cenários do AC-7 |
| `memory/work_log.md` | Atualizar | Registrar: auditor funcional, lore consultado, smoke test realizado |

---

## Notas Importantes

**Sobre o comportamento não-bloqueante:**
O IP Auditor é um sistema de aviso para Mauro — não um gate. Mauro vê os warnings na fila de aprovação e decide se o conteúdo vai ou não. O sistema nunca descarta conteúdo automaticamente por inconsistência de lore. Isso é intencional e inviolável.

**Sobre o gap do "ponto de vista público":**
A verificação de lore verifica consistência com backstory, personalidade e arquétipo — não com o ponto de vista público da Zenya, que ainda está indefinido (gate de Mauro, conforme PRD). O auditor não valida o que ainda não foi definido.

**Sobre o custo do Haiku:**
A chamada ao Claude Haiku para verificação semântica adiciona ~0.5-1s por peça auditada e custo de ~$0.001 por auditoria. Para o volume atual (< 20 peças/dia), é desprezível.

---

*@dev (Nox) — Wave 1, Sprint EPIC-WAVE1*
*Sparkle AIOX Story W1-CHAR-1 — 2026-04-07*
