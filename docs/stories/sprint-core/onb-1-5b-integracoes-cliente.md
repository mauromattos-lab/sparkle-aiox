---
epic: EPIC-ONBOARDING — Zenya Onboarding System E2E
story: ONB-1.5b
title: Fase 4 — Configuração de Integrações do Cliente (Google + E-commerce)
status: Ready for Review
priority: Média
executor: "@dev (implementação) -> @qa (validação) -> @devops (deploy)"
sprint: Sprint Core (2026-04-05+)
depends_on: [ONB-1.5a — Config Técnica n8n + Z-API (deve iniciar em paralelo quando viável)]
unblocks: [ONB-1.6 — Teste Interno QA (quando perfil do cliente usa agenda ou e-commerce)]
estimated_effort: "10-14h (@dev 8-10h + @qa 2-3h + @devops 1h)"
prd: docs/prd/zenya-onboarding-system-prd.md (FR13, FR14, FR15, Story 1.5b)
---

# Story ONB-1.5b — Fase 4: Configuração de Integrações do Cliente

## Story

**Como** sistema de onboarding,
**Quero** provisionar automaticamente as integrações externas necessárias para cada perfil de cliente,
**Para que** a Zenya do cliente tenha acesso a Calendar, Drive e e-commerce desde o go-live sem configuração manual.

---

## Contexto Técnico

**Estado atual:**
- Google Calendar está em produção para clientes existentes (contas gerenciadas pela Sparkle)
- Loja Integrada e Nuvemshop: handlers existem (`loja_integrada_query`) mas não há provisioning automatizado
- Esta story **não tem código base** — começa do zero

**Arquivos relevantes:**
- `runtime/onboarding/` — onde criar `google_provisioner.py` e `ecommerce_provisioner.py`
- `runtime/tasks/handlers/loja_integrada_query.py` — handler existente para consultas (referência)
- `runtime/onboarding/router.py` — adicionar endpoints de configuração

**Perfis de integração:**

| Perfil | Trigger | Integrações |
|--------|---------|-------------|
| Serviço com agenda | `has_scheduling = true` no intake | Google Calendar + Drive |
| E-commerce | `business_type = ecommerce` no intake | Loja Integrada ou Nuvemshop + Drive |
| Serviço sem agenda | default | Drive apenas |

---

## Acceptance Criteria

### AC1 — Google Drive (todos os clientes)
1. Criar `runtime/onboarding/google_provisioner.py`
2. Função `provision_drive(client_id, business_name) -> DriveResult`
3. Cria pasta no Google Drive da Sparkle com estrutura padrão:
   ```
   {business_name}/
   ├── materiais/fotos/
   ├── materiais/docs/
   ├── materiais/videos/
   └── contratos/
   ```
4. Armazenar `google_drive_folder_id` em `zenya_clients`
5. Compartilhar pasta com email do cliente (se fornecido no intake)

### AC2 — Google Calendar (clientes com agenda)
1. Função `provision_calendar(client_id, business_name, business_hours) -> CalendarResult`
2. Cria (ou reutiliza) calendário Google associado à conta Sparkle gerenciada
3. Configura horários de atendimento com base nos dados do intake (`business_hours`)
4. Credential OAuth cadastrada/atualizada no n8n para a conta
5. Armazenar `google_calendar_id` + `google_account_email` em `zenya_clients`

### AC3 — E-commerce: Loja Integrada
1. Função `provision_loja_integrada(client_id, api_key) -> EcommerceResult`
2. Valida API key via `GET /v1/orders?per_page=1` (smoke test)
3. Armazenar `loja_integrada_api_key` em `zenya_clients` (campo já existe em clientes como Fun Personalize)
4. Registra em `onboarding_events`: `ecommerce_configured = true`

### AC4 — E-commerce: Nuvemshop
1. Função `provision_nuvemshop(client_id, store_id, access_token) -> EcommerceResult`
2. Valida credenciais via API Nuvemshop
3. Armazenar `nuvemshop_store_id` e `nuvemshop_token` em `zenya_clients`

### AC5 — Coleta de materiais
1. Endpoint `POST /onboarding/{session_id}/upload-materials` recebe arquivos
2. Upload automático para a pasta Drive do cliente (`materiais/docs/` ou subpasta adequada)
3. Friday notifica Mauro quando materiais chegam: *"Materiais recebidos de {business_name} — organizados no Drive"*

### AC6 — Perfil determina o fluxo
1. `onboarding/service.py` chama provisioners corretos baseado no perfil detectado no intake
2. Se perfil não requer integração → step marcado como `skipped` (não `failed`)
3. Gate 2 de intake completo NÃO é bloqueado por integrações opcionais

### AC7 — Campos no banco
Migration (se necessária) adiciona em `zenya_clients`:
- `google_drive_folder_id` (text, nullable)
- `google_calendar_id` (text, nullable)
- `google_account_email` (text, nullable)
- `loja_integrada_api_key` (text, nullable)
- `nuvemshop_store_id` (text, nullable)
- `nuvemshop_token` (text, nullable)

> Verificar se campos já existem antes de criar migration.

---

## Integration Verification

| IV | Verificação |
|----|------------|
| **IV1** | Criar pasta Drive para cliente fictício: confirmar estrutura de subpastas |
| **IV2** | Calendar: horários configurados visíveis no Google Calendar da Sparkle |
| **IV3** | Loja Integrada: validar API key fictícia retorna erro esperado (não 500) |
| **IV4** | Nuvemshop: idem |
| **IV5** | Perfil "sem agenda": Calendar step aparece como `skipped`, não `failed` |
| **IV6** | Upload de material: arquivo aparece na pasta correta do Drive |
| **IV7** | Clientes existentes (Plaka, Fun Personalize): nenhum campo sobrescrito |

---

## Out of Scope

- Criação de nova conta Google por cliente (usa contas gerenciadas pela Sparkle já existentes)
- Integração com outras plataformas de e-commerce além de Loja Integrada e Nuvemshop
- Interface de upload para o cliente final (o upload é feito por Mauro ou pelo agente)
- Automatização de Asaas próprio do cliente (FR5 do PRD — complexidade alta, backlog)

---

## Definition of Done

- [x] `google_provisioner.py` criado com Drive + Calendar
- [x] `ecommerce_provisioner.py` criado (Loja Integrada + Nuvemshop)
- [x] `onboard_client.py` step 5b chama provisioners por perfil (Drive sempre, Calendar se has_scheduling, ecommerce se business_type=ecommerce)
- [x] Migration 014 aplicada (campos google_*, loja_integrada_api_key, nuvemshop_* em zenya_clients)
- [ ] Upload de materiais → Drive funcional (requer GOOGLE_SERVICE_ACCOUNT_JSON)
- [ ] Friday notifica upload recebido (requer Drive funcional)
- [ ] @qa: IV1–IV7 passam (IV1/2/6 pendentes — requer GOOGLE_SERVICE_ACCOUNT_JSON)
- [ ] @devops: deploy em produção

## Dev Agent Record

### Completion Notes
- `google_provisioner.py` criado em `runtime/onboarding/` — retorna `manual_required=True` se `GOOGLE_SERVICE_ACCOUNT_JSON` ausente (graceful degradation)
- `ecommerce_provisioner.py` criado — Loja Integrada valida via GET /v1/orders (302=redirect/inválido, 401=inválido), Nuvemshop valida 401
- `onboard_client.py` step 5b adicionado: Drive (sempre), Calendar (se `has_scheduling=true`), E-commerce (se `business_type=ecommerce`)
- Profile "sem agenda": step Calendar marcado como "skipped (sem agenda)" — não failed
- **Blocker: GOOGLE_SERVICE_ACCOUNT_JSON** — necessário para IV1/2/6. Mauro precisa fornecer (ou confirmar conta gerenciada).
- IV3 ✅ Loja Integrada key inválida → 302 (não 500)
- IV4 ✅ Nuvemshop inválida → 401 (não 500)
- IV5 ✅ Calendar step "skipped" implementado
- IV7 ✅ Provisioners só atualizam campos específicos — não sobrescrevem campos existentes

### Change Log
- `runtime/onboarding/google_provisioner.py` — criado
- `runtime/onboarding/ecommerce_provisioner.py` — criado
- `runtime/tasks/handlers/onboard_client.py` — step 5b adicionado

---

## Notas para @dev

1. **Credenciais Google:** A Sparkle já tem conta Google gerenciada com acesso a Calendar/Drive. Verificar `.env` para `GOOGLE_SERVICE_ACCOUNT_JSON` ou `GOOGLE_OAUTH_TOKEN` antes de implementar autenticação.

2. **Loja Integrada — cliente Fun Personalize:** API key estava aguardando (client_fun_personalize.md). Quando a Julia enviar, o provisioner desta story deve conseguir configurá-la automaticamente.

3. **Prioridade de campos no banco:** Antes de criar migration, executar `SELECT column_name FROM information_schema.columns WHERE table_name = 'zenya_clients'` no Supabase para verificar o que já existe.

4. **Esta story pode rodar em paralelo com 1.5a** para o setup do Drive/Calendar, mas o teste completo da Zenya (story 1.6) depende de ambas estarem done.

— River, removendo obstáculos 🌊
