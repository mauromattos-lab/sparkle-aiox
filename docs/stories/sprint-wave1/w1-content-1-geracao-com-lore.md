---
epic: EPIC-WAVE1
story: W1-CONTENT-1
title: Conteúdo — Geração com Lore da Zenya Injetado no Prompt
status: Ready for Dev
priority: Alta
executor: "@dev -> @devops -> @qa"
sprint: Wave 1 — Domain Activation (2026-04-07+)
depends_on:
  - W0-CHAR-1 (lore canônico disponível — sparkle-lore 33+ chunks + character_lore 13 entries)
  - W1-CHAR-1 (IP Auditor funcional com verificação semântica — valida saída desta story)
unblocks:
  - W1-BRAIN-1 (conteúdo aprovado como sinal de qualidade para o Brain — flywheel ativo)
estimated_effort: "5-7h (@dev 4-6h + @qa 1h)"
prd_reference: docs/prd/domain-content-wave2-prd.md
architecture_reference: docs/architecture/domain-content-wave2-architecture.md
---

# Story W1-CONTENT-1 — Geração de Conteúdo com Lore da Zenya Injetado

## Story

**Como** pipeline de conteúdo da Zenya,
**Quero** consultar o Brain (`namespace='sparkle-lore'`) e a tabela `character_lore` antes de gerar cada post, script ou carrossel, e injetar os fragmentos de lore mais relevantes no prompt do `copy_specialist.py`,
**Para que** todo conteúdo gerado seja intrinsecamente consistente com o personagem da Zenya — não por revisão posterior, mas por design do prompt de geração.

---

## Contexto Técnico

**Estado atual — como a geração funciona hoje:**

O pipeline de conteúdo segue a máquina de estados em `pipeline.py`:

```
briefed → image_generating → image_done → (copy + video em paralelo) → video_done → [ip_audit] → pending_approval
```

O módulo responsável pela geração de copy é `runtime/content/copy_specialist.py`. Ele recebe o `content_brief` e gera `voice_script`, `caption` e `hashtags`. O prompt atual usa o tema e o estilo do brief, mas **não consulta o Brain nem `character_lore`** — o lore da Zenya não está presente no momento da geração.

Isso significa que o IP Auditor (W1-CHAR-1) detecta inconsistências *depois* que o conteúdo foi gerado. A solução desta story vai um passo antes: injetar lore *antes* da geração, para que o copy_specialist produza conteúdo já alinhado com o personagem.

**Estado após W0-CHAR-1 (disponível para uso):**

```
Brain namespace 'sparkle-lore':
  - 33+ chunks approved
  - metadata: { character: 'zenya', lore_type: 'canonical' | 'bible' }
  - acessível via POST /brain/query ou supabase.rpc('match_brain_chunks')

character_lore table:
  - 13 entries, character_slug='zenya'
  - lore_type: backstory, personality, arc, belief, relationship
  - is_public=true, reveal_after=NULL (disponível imediatamente)
  - acessível via lore_loader.load_public_lore(character_id)
```

**O que esta story implementa:**

Um novo módulo `lore_injector.py` que, dado um `content_brief`, recupera os fragmentos de lore mais relevantes para o tema da peça e retorna um bloco de contexto para ser inserido no prompt do `copy_specialist`.

**Fluxo após implementação:**

```
content_brief (tema, estilo, plataforma)
    │
    ├── lore_injector.get_lore_context(brief)
    │   ├── Brain query: POST /brain/query { namespace: 'sparkle-lore', query: tema, top_k: 3 }
    │   └── character_lore query: WHERE character_slug='zenya' AND lore_type IN ('personality', 'arc', 'belief')
    │   → lore_context: string com fragmentos relevantes
    │
    └── copy_specialist.generate(brief, lore_context=lore_context)
        → voice_script, caption, hashtags
        (gerados com lore da Zenya no contexto)
```

**Arquivos relevantes:**

```
sparkle-runtime/runtime/content/copy_specialist.py    ← modificar (adicionar lore_context ao prompt)
sparkle-runtime/runtime/content/pipeline.py           ← modificar (chamar lore_injector antes de copy)
sparkle-runtime/runtime/characters/lore_loader.py     ← reutilizar (padrão de consulta character_lore)
sparkle-runtime/runtime/brain/                        ← consultar (namespace sparkle-lore)
```

**Relação com IP Auditor (W1-CHAR-1):**

Esta story e W1-CHAR-1 são complementares — não substitutos. O `lore_injector` injeta lore *antes* da geração para aumentar a probabilidade de consistência. O IP Auditor valida *depois* para detectar o que escapou. O pipeline fica:

```
lore_injector → copy_specialist → [ip_audit] → pending_approval
```

---

## Critérios de Aceitação

### AC-1 — Módulo `lore_injector.py` criado

- [x] Arquivo `sparkle-runtime/runtime/content/lore_injector.py` criado com interface pública:
  ```python
  async def get_lore_context(brief: dict, max_chars: int = 1500) -> str:
      """
      Dado um content_brief, retorna bloco de contexto de lore da Zenya.
      Combina: top-3 chunks relevantes do Brain (sparkle-lore) + entries de character_lore (personality, arc, belief).
      Retorna string formatada pronta para inserir no prompt do copy_specialist.
      Retorna "" se lore indisponível — nunca bloqueia.
      """
  ```
- [x] Função retorna `""` gracefully se Brain indisponível ou `character_lore` vazio
- [x] `max_chars` limita o bloco de lore para não exceder contexto do LLM
- [x] Tempo máximo de execução: 3s (timeout configurável via env `LORE_INJECTOR_TIMEOUT_SECONDS`, default 3)

### AC-2 — Brain query para lore relevante ao tema

- [x] `lore_injector` executa query no Brain com `namespace='sparkle-lore'` usando o campo `theme` do brief como query de similaridade
- [x] Query retorna `top_k=3` chunks mais relevantes
- [x] Chunks são formatados como:
  ```
  [LORE] {lore_type}: {canonical_text[:200]}
  ```
- [x] Chunks com `curation_status != 'approved'` são excluídos da injeção

### AC-3 — character_lore entries para personalidade e arco

- [x] `lore_injector` consulta `character_lore` WHERE `character_slug='zenya'` AND `lore_type IN ('personality', 'arc', 'belief')` AND `is_public=true` AND `reveal_after IS NULL OR reveal_after <= NOW()`
- [x] Entries são incluídas no bloco de contexto antes dos chunks do Brain (maior peso estrutural)
- [x] Formato:
  ```
  [PERSONAGEM] {lore_type}: {content[:300]}
  ```

### AC-4 — Integração com `copy_specialist.py`

- [x] `copy_specialist.generate()` aceita parâmetro opcional `lore_context: str = ""`
- [x] Quando `lore_context` não vazio, é inserido no system prompt antes das instruções de geração:
  ```
  === LORE CANÔNICO DA ZENYA (use como guia de consistência) ===
  {lore_context}
  === FIM DO LORE ===
  ```
- [x] Quando `lore_context` vazio, comportamento atual é mantido sem degradação
- [x] O `lore_context` não substitui as instruções de estilo e plataforma — é adicionado como contexto de personagem

### AC-5 — Integração no pipeline (`pipeline.py`)

- [x] `pipeline.py` chama `lore_injector.get_lore_context(brief)` imediatamente antes de chamar `copy_specialist.generate()`
- [x] O resultado de `get_lore_context()` é passado como `lore_context` para `copy_specialist.generate()`
- [x] A chamada ao `lore_injector` é envolvida em try/except — se falhar, pipeline continua sem lore_context (não bloqueia geração)
- [x] `pipeline_log` registra entry de log com quantidade de lore injetado:
  ```json
  { "event": "lore_injected", "chars_injected": 1200, "chunks_used": 3, "lore_entries_used": 2, "at": "ISO" }
  ```

### AC-6 — Qualidade observável do conteúdo gerado

- [x] Após implementação, gerar 3 peças de teste com temas distintos (ex: tema de autoconhecimento, tema de tecnologia, tema de cotidiano)
- [x] Verificar em `pipeline_log` que `lore_injected` aparece com `chars_injected > 0` para todas as 3 peças
- [x] IP Auditor (W1-CHAR-1) deve retornar `lore_compliance='COMPATIVEL'` para as 3 peças geradas (evidência de que a injeção melhora a qualidade)
- [ ] Mauro aprova pelo menos 2 das 3 peças sem solicitar revisão de personagem

### AC-7 — Testes automatizados

- [x] `tests/content/test_lore_injector.py` cobre: lore disponível (retorna string não-vazia), Brain indisponível (retorna `""`), character_lore vazio (retorna apenas chunks do Brain), timeout (retorna `""` sem exception)
- [x] `tests/content/test_copy_specialist_lore.py` cobre: geração com `lore_context` (lore aparece no prompt enviado ao LLM), geração sem `lore_context` (comportamento não alterado)
- [x] `pytest tests/content/test_lore_injector.py tests/content/test_copy_specialist_lore.py` passa no VPS (10/10)

---

## Definition of Done

- [x] Todos os ACs passando (AC-6 parcial — aprovação do Mauro pendente)
- [x] `lore_injector.py` criado e integrado ao pipeline
- [x] `copy_specialist.py` recebe e usa `lore_context` no prompt
- [x] `pipeline_log` registra `lore_injected` em todas as peças geradas após o deploy
- [x] 3 peças de teste geradas com lore injetado — `pipeline_log` confirmado (1287chars, 3 chunks, 2 entries)
- [x] IP Auditor retorna `COMPATIVEL` para as 3 peças de teste (validação cruzada — 3/3 COMPATIVEL)
- [ ] @qa validou integração: lore aparece no prompt, pipeline não regride
- [x] @devops confirmou deploy no VPS com smoke test (systemctl restart OK, 10 unit tests passing)
- [x] Nenhum conteúdo bloqueado por erro do lore_injector (comportamento não-bloqueante verificado)

---

## Tarefas Técnicas

- [x] **T1 — Criar `runtime/content/lore_injector.py`:**
  - Implementar `get_lore_context(brief, max_chars=1500)` com as duas fontes (Brain + character_lore)
  - Query Brain: usar padrão do `ip_auditor.py` mas com namespace correto e filtro `curation_status='approved'`
  - Query character_lore: reutilizar padrão do `lore_loader.load_public_lore()` com filtro de `lore_type`
  - Combinar e truncar ao `max_chars`
  - Implementar timeout via `asyncio.wait_for()` com `LORE_INJECTOR_TIMEOUT_SECONDS`

- [x] **T2 — Modificar `runtime/content/copy_specialist.py`:**
  - Adicionar parâmetro `lore_context: str = ""` em `generate()` e `apply_copy_to_piece()`
  - Inserir bloco de lore no system prompt quando não vazio
  - Garantir que as instruções de estilo, plataforma e tom continuam intactas

- [x] **T3 — Modificar `runtime/content/pipeline.py`:**
  - Importar `lore_injector`
  - Chamar `get_lore_context(brief)` antes de `copy_specialist.generate()`
  - Passar resultado como `lore_context`
  - Envolver em try/except com fallback para `""` e log de warning
  - Adicionar entry `lore_injected` no `pipeline_log`

- [x] **T4 — Verificar `character_id` vs `character_slug` em character_lore:**
  - `character_lore` não tinha `character_slug` — adicionada via migration 018_character_lore_slug.sql
  - Backfill feito automaticamente a partir da tabela `characters`
  - Índice `idx_character_lore_character_slug` criado

- [x] **T5 — Escrever testes:**
  - `tests/content/test_lore_injector.py` — 6 cenários com mocks (todos passando)
  - `tests/content/test_copy_specialist_lore.py` — 4 cenários com mock do Claude (todos passando)

- [x] **T6 — Gerar 3 peças de teste em produção:**
  - 3 peças geradas com temas: autoconhecimento, tecnologia, cotidiano
  - `pipeline_log` confirmado: lore_injected=1287chars, 3 Brain chunks, 2 char_lore entries
  - IP Auditor: 3/3 COMPATIVEL, 0 warnings

- [ ] **T7 — Atualizar `work_log.md`:**
  - Registrar: lore_injector criado, copy_specialist atualizado, smoke test OK

---

## Dependências

**Esta story depende de:**
- W0-CHAR-1 (lore canônico disponível — `sparkle-lore` 33+ chunks, `character_lore` 13 entries) — **Done**
- W1-CHAR-1 (IP Auditor funcional) — **deve ser concluída antes do smoke test desta story** (AC-6 depende do auditor para validar qualidade)

**Esta story desbloqueia:**
- W1-BRAIN-1 — Flywheel Content→Brain: conteúdo aprovado pelo Mauro passa a ser ingerido no Brain como sinal de qualidade. Só faz sentido iniciar o flywheel quando o conteúdo gerado já tem consistência de lore.

**Referências de código existente (ler antes de implementar):**
- `runtime/content/ip_auditor.py` — padrão de query Brain já implementado (reutilizar em T1)
- `runtime/characters/lore_loader.py` — padrão de consulta `character_lore` (reutilizar em T1)
- `runtime/content/copy_specialist.py` — ponto de modificação (T2)
- `runtime/content/pipeline.py` — ponto de integração (T3)

---

## Pipeline AIOS

| Etapa | Agente | Entrega |
|-------|--------|---------|
| T1 — Criar lore_injector | @dev | `lore_injector.py` com Brain + character_lore |
| T2 — Modificar copy_specialist | @dev | `generate()` aceita e usa `lore_context` |
| T3 — Integrar no pipeline | @dev | `pipeline.py` chama injector antes de copy |
| T4 — Verificar schema character_lore | @dev | Consulta por `character_slug` validada |
| T5 — Testes automatizados | @dev | `test_lore_injector.py` + `test_copy_specialist.py` passando |
| Deploy VPS | @devops | Novos módulos em produção, smoke test |
| Smoke test + validação cruzada | @qa | 3 peças geradas com lore, IP Auditor COMPATIVEL |

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `sparkle-runtime/runtime/content/lore_injector.py` | Criar | Novo módulo: recupera lore do Brain + character_lore e formata para injeção |
| `sparkle-runtime/runtime/content/copy_specialist.py` | Modificar | Adicionar `lore_context` ao prompt de geração |
| `sparkle-runtime/runtime/content/pipeline.py` | Modificar | Chamar `lore_injector` antes de `copy_specialist`, registrar `lore_injected` no log |
| `sparkle-runtime/runtime/characters/lore_loader.py` | Ler | Padrão de consulta `character_lore` a reutilizar |
| `sparkle-runtime/runtime/content/ip_auditor.py` | Ler | Padrão de query Brain a reutilizar em lore_injector |
| `sparkle-runtime/tests/content/test_lore_injector.py` | Criar | Testes do módulo lore_injector |
| `sparkle-runtime/tests/content/test_copy_specialist.py` | Criar | Testes de integração copy_specialist com lore_context |
| `memory/work_log.md` | Atualizar | Registrar implementação e smoke test |

---

## Notas Importantes

**Sobre a sequência com W1-CHAR-1:**
Esta story e W1-CHAR-1 podem ser desenvolvidas em paralelo por @dev, mas o smoke test completo (AC-6) depende do IP Auditor estar funcional. @dev pode implementar T1-T5 desta story em paralelo com W1-CHAR-1, e só executar T6 após W1-CHAR-1 estar deployed.

**Sobre `character_slug` vs `character_id`:**
O `lore_loader.py` usa `character_id` (UUID) porque foi escrito quando o handler passava o ID do banco. O `lore_injector` deve preferir `character_slug='zenya'` — é mais legível, mais robusto em multi-ambiente, e o índice na tabela cobre essa coluna. Se `character_lore` não tiver índice em `character_slug`, criar na migration de W1-CHAR-1 ou como migration incremental aqui.

**Sobre o `max_chars` do lore_context:**
1500 chars equivale a ~375 tokens. O prompt total do copy_specialist (sistema + brief + lore) deve ficar abaixo de 4000 tokens para Claude Haiku e abaixo de 8000 para Claude Sonnet. Testar que o bloco de lore não empurra o prompt além dos limites do modelo configurado.

**Sobre o flywheel (W1-BRAIN-1):**
Esta story habilita o flywheel de forma indireta: conteúdo gerado com lore tende a ser aprovado mais frequentemente → aprovações são o sinal de qualidade que o flywheel usa para ingerir conteúdo de volta no Brain. Sem lore no prompt, o flywheel ingeriria conteúdo genérico como conhecimento de Zenya — o que degradaria o Brain ao longo do tempo.

---

*@dev (Nox) — Wave 1, Sprint EPIC-WAVE1*
*Sparkle AIOX Story W1-CONTENT-1 — 2026-04-07*
