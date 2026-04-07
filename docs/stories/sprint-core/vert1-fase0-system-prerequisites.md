# VERT1-F0: Fase 0 — Pre-requisitos do Sistema para Vertical Zenya

**Sprint:** Vertical 1 - Clientes/Zenya
**Status:** FUNCIONAL
**Pipeline:** Processo 3 (Correcao) + Processo 4 (Planejamento)
**Criado por:** @architect (Aria) + @analyst — blueprint vertical-1-zenya-blueprint.md
**Referencia:** docs/architecture/vertical-1-zenya-blueprint.md

---

## Contexto

Antes de migrar qualquer cliente do n8n para o Runtime, ha 5 acoes de sistema que precisam ser feitas uma unica vez. Sem elas, cada migracao individual vai ter fricao desnecessaria.

**Regra:** Nenhuma dessas acoes toca no fluxo de clientes em producao. Tudo e interno.

---

## F0-1: Padronizar Client ID (UUID como canonico)

**Problema:** `zenya_clients` usa slug (`confeitaria-dona-geralda`) enquanto `clients`, `zenya_knowledge_base`, e `brain_chunks` usam UUID (`9a50811b-...`). Sem FK linking.

**Fix:** Atualizar `zenya_clients` para usar UUID de `clients.id`. Manter slug como campo `display_slug` se necessario.

### Acceptance Criteria
- [x] `zenya_clients.client_id` do Alexsandro atualizado de `confeitaria-dona-geralda` para UUID correspondente de `clients.id`
- [x] `zenya_clients.client_id` do Fun Personalize atualizado de `fun-personalize` para UUID correspondente
- [x] Coluna `display_slug` adicionada em `zenya_clients` (para URL amigavel se necessario)
- [x] Router `/zenya/webhook/{client_id}` funciona com UUID
- [x] Router tambem aceita slug como fallback (busca por display_slug)

---

## F0-2: Criar Registros zenya_clients Faltantes

**Problema:** Douglas (Ensinaja) e Luiza (Plaka) nao existem em `zenya_clients`. Sao clientes Zenya ativos no n8n sem representacao no Runtime.

**Fix:** Criar registros para ambos usando UUID de `clients.id`.

### Acceptance Criteria
- [x] Douglas/Ensinaja tem registro em `zenya_clients` com `client_id` = UUID de `clients`
- [x] Luiza/Plaka tem registro em `zenya_clients` com `client_id` = UUID de `clients`
- [x] Ambos com `active=false` (serao ativados na migracao individual)
- [x] Campos: business_name, phone preenchidos a partir de `clients`

---

## F0-3: Extrair DNA dos Clientes com KB

**Problema:** Tabela `client_dna` esta completamente vazia. Alexsandro tem 193 KB entries e Douglas tem 35 — material suficiente para extrair DNA.

**Fix:** Rodar DNA extraction para Alexsandro e Douglas via endpoint existente.

### Acceptance Criteria
- [x] `POST /brain/extract-dna/{client_id}` executado para Alexsandro (UUID)
- [x] `POST /brain/extract-dna/{client_id}` executado para Douglas (UUID)
- [x] `client_dna` tem pelo menos 3 categorias preenchidas para cada
- [x] Se extraction falhar (sem credito Anthropic), documentar como blocker

**Status F0-3:** CONCLUIDO (2026-04-05)
- Alexsandro: 24 items em 6 categorias (produtos=7, faq=5, diferenciais=4, publico_alvo=4, regras=2, objecoes=2). soul_prompt_generated OK.
- Douglas: 51 items em 8 categorias (produtos=12, faq=9, regras=8, objecoes=6, diferenciais=5, publico_alvo=5, persona=4, tom=2). soul_prompt_generated OK.
- Fixes aplicados: constraint `client_dna_dna_type_check` duplicada removida, max_tokens aumentado de 4096 para 8192 (truncava JSON de clientes com muitos chunks).

---

## F0-4: Atribuir Brain Chunks Orfaos

**Problema:** 513 brain_chunks tem `brain_owner = NULL`. Sao provavelmente conteudo interno Sparkle/Orion.

**Fix:** Atribuir `brain_owner = 'sparkle-internal'` para chunks orfaos. Definir convencao de namespace para clientes: `client:{uuid}`.

### Acceptance Criteria
- [x] Chunks com `brain_owner IS NULL` atualizados para `brain_owner = 'sparkle-internal'` (513 chunks)
- [x] Zero chunks orfaos apos fix
- [x] Convencao documentada: clientes usam `brain_owner = '{client_uuid}'`

---

## F0-5: Atribuir Conversation History Orfao

**Problema:** 146 registros em `conversation_history` tem `client_id = NULL`. Sao conversas de producao (Friday/Mauro) sem atribuicao.

**Fix:** Atribuir ao client_id interno (`sparkle-internal`) ou ao Mauro.

### Acceptance Criteria
- [x] Mensagens com `client_id IS NULL` atribuidas ao ID correto (sparkle-internal) — 146 registros (Friday/Mauro sessions)
- [x] Zero mensagens orfas apos fix

---

## File List

| Arquivo/Recurso | Mudanca |
|---------|---------|
| Supabase `zenya_clients` | UPDATE client_id para UUID (F0-1), INSERT Douglas + Plaka (F0-2) |
| Supabase `client_dna` | INSERT via extraction endpoint (F0-3) |
| Supabase `brain_chunks` | UPDATE brain_owner orfaos (F0-4) |
| Supabase `conversation_history` | UPDATE client_id orfaos (F0-5) |
| `sparkle-runtime/runtime/zenya/router.py` | Fallback slug lookup (F0-1) |

---

## Pipeline AIOS

1. **@architect (Aria)** — Blueprint aprovado (vertical-1-zenya-blueprint.md)
2. **@analyst** — Dados levantados (IDs, contagens, gaps)
3. **@dev** — Implementar F0-1 a F0-5
4. **@qa** — Validar dados no banco + testar webhook com UUID
5. **@devops** — Deploy se houver mudanca de codigo (F0-1 router)
