# Vertical 1 — Clientes/Zenya: Migration Blueprint

**Author:** @architect (Aria) | **Date:** 2026-04-05 | **Status:** ACTIVE

---

## What "100% on Runtime" Means

A Zenya client is fully on Runtime when ALL of these are true:

| Layer | Requirement | How to verify |
|-------|-------------|---------------|
| **1. zenya_clients** | Row exists with `active=true`, Z-API creds populated | `GET /zenya/clients` returns the client |
| **2. Z-API webhook** | Points to `POST /zenya/webhook/{client_id}` on Runtime | Z-API dashboard shows Runtime URL |
| **3. Soul prompt** | `soul_prompt` or `soul_prompt_generated` populated | `GET /zenya/clients/{id}/dna/preview-prompt` shows source != "fallback" |
| **4. Knowledge base** | 20+ rows in `zenya_knowledge_base` for this client_id | SQL count |
| **5. Brain chunks** | Client content ingested into `brain_chunks` (namespace=client_id or general) | Brain query returns results |
| **6. DNA extracted** | `client_dna` JSONB populated (3+ of 8 categories) | `GET /zenya/clients/{id}/dna` shows filled categories |
| **7. Message history** | `zenya_messages` table used (not n8n Chatwoot) | Runtime logs show `send_character_message` |
| **8. n8n OFF** | Legacy n8n workflows deactivated for this client | n8n API check or manual confirmation |

**Minimum viable:** Layers 1-3 + 8 are enough to go live. Layers 4-7 make the Zenya actually smart.

---

## Migration Architecture: n8n to Runtime

```
BEFORE (n8n path):
  WhatsApp -> Z-API -> n8n webhook -> n8n workflow (AI node + KB lookup) -> Z-API -> WhatsApp

AFTER (Runtime path):
  WhatsApp -> Z-API -> POST /zenya/webhook/{client_id}
    -> _get_client_config() from zenya_clients
    -> _process_zenya_message() creates runtime_task (send_character_message)
    -> handler: detect intent -> enrich context (e-commerce, DNA, history) -> call_claude
    -> _send_zenya_message() via client's Z-API creds -> WhatsApp
```

### Migration Steps (per client)

```
1. PREPARE (no downtime)
   a. Create row in zenya_clients with client_id, business_name, soul_prompt, Z-API creds
   b. Ingest client content into Brain (site, docs, Instagram)
   c. Extract DNA via POST /brain/extract-dna/{client_id}
   d. Verify soul_prompt_generated looks good via /dna/preview-prompt
   e. Test: curl POST /zenya/webhook/{client_id} with fake payload

2. SWITCH (30-second cutover)
   a. Change Z-API webhook URL from n8n to Runtime
   b. Send test message from a known number
   c. Confirm response arrives via Runtime logs

3. VALIDATE (24h observation)
   a. Monitor zenya_messages for new entries
   b. Check error logs for handler failures
   c. Compare response quality vs n8n baseline

4. DECOMMISSION (after 48h stable)
   a. Deactivate n8n workflows for this client
   b. Update clients table: has_zenya=true, zenya_workflow_id=null
   c. Mark in agent-queue as FUNCIONAL
```

---

## Current State: Two Parallel Tables

There is a data model split that must be resolved per client:

| Table | Purpose | Used by |
|-------|---------|---------|
| `clients` | Master CRM (name, MRR, flags, n8n workflow IDs) | Billing, cockpit, legacy |
| `zenya_clients` | Runtime multi-tenant config (soul_prompt, Z-API creds, DNA) | Runtime Zenya router |

**Rule:** Every Zenya client needs a row in BOTH tables. The `client_id` in `zenya_clients` should match the `id` in `clients` (UUID) or use a slug. Currently inconsistent: `confeitaria-dona-geralda` (slug) vs `9a50811b-...` (UUID in clients).

**Action needed:** Standardize on UUID from `clients.id` as the canonical `client_id` in `zenya_clients`. This is a one-time fix.

---

## Client-by-Client Assessment

### Priority Order (recommended)

| # | Client | Rationale |
|---|--------|-----------|
| 1 | Alexsandro / Confeitaria | Already on Runtime (OPS-2 FUNCIONAL). Validate + fix data model. |
| 2 | Ensinaja / Douglas | Data extracted, OPS-3 ready. Quick win: R$650/mês. |
| 3 | Plaka / Luiza | Simple SAC, on n8n, low risk migration. |
| 4 | Fun Personalize / Julia | Code ready, blocked on credentials. Unblock = go live. |
| 5 | Vitalis / Joao Lucio | No Zenya yet. Upsell opportunity, not migration. |
| 6 | Gabriela / Consorcio | No Zenya yet. Meta Ads only. Future upsell. |

---

### 1. Alexsandro / Confeitaria (Doceria Dona Geralda)

**Status:** Partially on Runtime. OPS-2 marked FUNCIONAL.

| Layer | Status | Detail |
|-------|--------|--------|
| zenya_clients | EXISTS | `client_id=confeitaria-dona-geralda`, active=true, has_zapi=true |
| Z-API webhook | ON RUNTIME | Pointing to `/zenya/webhook/confeitaria-dona-geralda` |
| Soul prompt | HAS manual | soul_prompt populated |
| KB | 193 items | In `zenya_knowledge_base` (client_id=`9a50811b-...` UUID) |
| Brain chunks | NONE client-specific | Only general/personal namespaces exist |
| DNA | EMPTY | `client_dna={}` |
| Message history | 0 in zenya_messages | History might be in n8n/Chatwoot still |
| n8n | UNCLEAR | `zenya_workflow_id=u7BDmAvPE4Sm6NXd` still in clients table |

**Gaps:**
- client_id mismatch: `confeitaria-dona-geralda` (zenya_clients) vs `9a50811b-...` (clients + KB)
- DNA not extracted
- Brain not ingested (client-specific namespace)
- n8n workflow status unclear (may still be active as fallback)

**Actions:**
1. Fix client_id alignment (update zenya_clients to use UUID, or update KB to use slug)
2. Ingest site content into Brain with client namespace
3. Run DNA extraction: `POST /brain/extract-dna/confeitaria-dona-geralda`
4. Confirm n8n workflow is OFF
5. Verify 729 messages (mentioned in OPS-2) are flowing through Runtime

**Effort:** ~2h @dev

---

### 2. Ensinaja / Douglas

**Status:** Not on Runtime. OPS-3 PENDENTE (data extracted, go-live blocked).

| Layer | Status | Detail |
|-------|--------|--------|
| zenya_clients | MISSING | No row exists |
| Z-API webhook | N/A | Still on n8n |
| Soul prompt | UNKNOWN | May exist in n8n workflow configs |
| KB | 35 items | In `zenya_knowledge_base` (client_id=`b1d89755-...`) |
| Brain chunks | NONE | 10 courses extracted per OPS-3 notes, but not in brain_chunks |
| DNA | N/A | No zenya_clients row |
| n8n | `zenya_workflow_id=agEnqd5797ugaxEp` | Active in n8n |

**Gaps:**
- No zenya_clients row at all
- Need Z-API instance credentials
- Need to create soul_prompt (or extract from n8n workflow)
- Brain ingest of the 10 courses data
- Phone: (12) 98197-4622

**Actions:**
1. Create zenya_clients row with client_id=`b1d89755-3314-4842-bb34-d33d95f0b6f4`
2. Extract soul_prompt from n8n workflow `agEnqd5797ugaxEp` via n8n API
3. Populate Z-API credentials (same instance or new one)
4. Ingest course data into Brain
5. Run DNA extraction
6. Switch Z-API webhook to Runtime
7. Deactivate n8n workflow

**Blocker:** OPS-3 says "segunda-feira" and needs Mauro for go-live signal.
**Effort:** ~3h @dev + Mauro approval

---

### 3. Plaka / Luiza (Plaka Acessorios)

**Status:** Not on Runtime. On n8n, SAC only.

| Layer | Status | Detail |
|-------|--------|--------|
| zenya_clients | MISSING | No row exists |
| Z-API webhook | N/A | On n8n |
| Soul prompt | EXISTS in n8n | 52 KB scripts created (per infra history) |
| KB | UNKNOWN count | Likely in Google Sheets (has `google_sheets_kb_id` field in clients) |
| Brain chunks | NONE | No client-specific content |
| DNA | N/A | No zenya_clients row |
| n8n | `zenya_workflow_id=371QcYGrXmZ1n8bV` | Active |

**Gaps:**
- No zenya_clients row
- Z-API credentials needed (may share Sparkle instance currently)
- KB might be in Google Sheets not Supabase
- Nuvemshop integration is OUT of scope (per contract)
- Need to migrate 52 KB scripts from Sheets to Supabase

**Actions:**
1. Create zenya_clients row with client_id=`cc89ab29-0ca5-4651-b0a8-a86416380f4a`
2. Extract soul_prompt from n8n workflow
3. Migrate KB from Google Sheets to `zenya_knowledge_base`
4. Populate Z-API credentials
5. Ingest site/Instagram into Brain
6. Run DNA extraction
7. Switch webhook, deactivate n8n

**Effort:** ~4h @dev (KB migration adds time)

---

### 4. Fun Personalize / Julia

**Status:** Code READY but blocked on credentials. BLOCK-03.

| Layer | Status | Detail |
|-------|--------|--------|
| zenya_clients | EXISTS | `client_id=fun-personalize`, active=**false**, has_zapi=**false** |
| Z-API webhook | NOT CONFIGURED | No Z-API instance |
| Soul prompt | HAS manual | soul_prompt populated |
| KB | 0 in Supabase | Not migrated yet |
| Brain chunks | NONE | No content ingested |
| DNA | EMPTY | `client_dna={}` |
| Loja Integrada | CODE READY | `send_character_message` handler has e-commerce intent detection |
| n8n | No workflow | `zenya_workflow_id=null` in clients |

**Gaps:**
- Z-API instance not created (Mauro action)
- Loja Integrada API key not received from Julia
- zenya_clients row exists but inactive and no Z-API creds
- No KB populated

**Actions (when unblocked):**
1. Mauro creates Z-API instance for Julia
2. Julia provides Loja Integrada API key
3. Update zenya_clients: set active=true, populate Z-API creds
4. Scrape funpersonalize.com.br, ingest into Brain
5. Run DNA extraction
6. Generate KB from Brain content
7. Configure Z-API webhook to Runtime
8. QA: test e-commerce intent detection (order tracking)

**Blocker:** Two external dependencies (Mauro + Julia). High-value client (R$897/mês).
**Effort:** ~2h @dev once unblocked

---

### 5. Vitalis / Joao Lucio

**Status:** Trafego pago only. No Zenya contract. BLOCK-06.

| Layer | Status | Detail |
|-------|--------|--------|
| zenya_clients | MISSING | No row |
| Zenya contract | NONE | Only paying for Meta Ads R$1.500/mês |
| Brain | NONE | No content |

**This is NOT a migration -- it is a new sale.**

**Strategy (from memory):** Use Z-API as passive listener on Joao Lucio's WhatsApp to collect conversation data. Demonstrate value. Upsell Zenya.

**Blocker:** Mauro needs to message Joao Lucio + connect WhatsApp to Z-API.
**Effort:** N/A for migration. Sales activity for Mauro.

---

### 6. Gabriela / Consorcio

**Status:** Meta Ads only. No Zenya contract. BLOCK-05.

| Layer | Status | Detail |
|-------|--------|--------|
| zenya_clients | MISSING | No row |
| Zenya contract | NONE | Only paying for Meta Ads R$750/mês |
| Meta Ads | PAUSED | 2 campaigns created, waiting for budget + creatives |

**This is NOT a migration -- it is a future upsell after Meta Ads delivers results.**

**Blocker:** Mauro needs to add budget + send creatives for existing campaigns.
**Effort:** N/A for migration. Depends on Meta Ads performance first.

---

## System-Level Actions (do once, benefit all)

### A. Client ID Standardization
Fix the `confeitaria-dona-geralda` slug vs UUID mismatch. Decide canonical format. Recommended: UUID everywhere, slug as display-only field.

**Effort:** 1h @dev, SQL migration

### B. n8n Soul Prompt Extractor
Build a utility to extract system_prompt from n8n workflow JSON (node "00-Configuracoes" -> Set node -> system_prompt assignment). Needed for Ensinaja + Plaka migration.

**Effort:** 1h @dev

### C. KB Migration Tool (Sheets to Supabase)
For clients whose KB lives in Google Sheets (Plaka at minimum), build a one-shot importer.

**Effort:** 2h @dev

### D. Brain Client Namespace Convention
Currently brain_chunks only has `general` and `personal` namespaces. Define convention: `client:{client_id}` namespace for per-client content. Update brain_ingest_pipeline to support client namespace.

**Effort:** 1h @dev

### E. Automated Onboarding Workflow (already exists)
The `onboarding_zenya` workflow template in `templates.py` already chains: scrape_site -> brain_ingest -> extract_dna -> generate_prompt -> notify. Use this for new clients instead of manual steps.

---

## Summary Dashboard

| Client | MRR | On Runtime? | Blocker | ETA |
|--------|-----|-------------|---------|-----|
| Alexsandro | R$500 | PARTIAL (fix data model) | None | 1 day |
| Ensinaja | R$650 | NO | Mauro go-live signal | 1 day after unblock |
| Plaka | R$297 | NO | KB migration | 2 days |
| Fun Personalize | R$897 | NO | Z-API + API key (external) | Unknown |
| Vitalis | R$1.500 | N/A (no Zenya) | Sales | N/A |
| Gabriela | R$750 | N/A (no Zenya) | Sales | N/A |

**Zenya MRR at risk (not on Runtime):** R$1.447/mês (Ensinaja + Plaka + Fun)
**Zenya MRR on Runtime (partial):** R$500/mês (Alexsandro)
**Total addressable Zenya MRR:** R$2.344/mês (4 clients with Zenya contracts)

---

## Execution Order

```
WAVE 1 (this week, no blockers):
  1. Fix Alexsandro data model + DNA extraction + confirm n8n is off
  2. System actions A + B (client_id standardization + n8n extractor)

WAVE 2 (needs Mauro once):
  3. Ensinaja go-live (create zenya_clients row, switch webhook)
  4. Plaka migration (extract prompt, migrate KB, switch webhook)

WAVE 3 (external dependency):
  5. Fun Personalize (when Z-API + API key arrive)

WAVE 4 (sales, not engineering):
  6. Vitalis upsell
  7. Gabriela upsell
```
