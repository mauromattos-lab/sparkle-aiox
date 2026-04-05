# SEC-1: P0 Security Fixes — Brownfield Audit

**Sprint:** Core Security
**Status:** AGUARDANDO_QA
**Pipeline:** Processo 3 (Correção de Bug) — sparkle-os-processes.md
**Criado por:** @architect (Aria) + @qa (auditoria brownfield 2026-04-04)

---

## Contexto

Auditoria brownfield identificou 5 vulnerabilidades P0 de segurança no sparkle-runtime que precisam de correção imediata antes de avançar para as verticais.

---

## P0-1: Handler Swap no Registry (Severidade: CRÍTICA)

**Arquivo:** `sparkle-runtime/runtime/tasks/registry.py` linhas 21-23
**Bug:** Imports estão trocados — `friday_initiative_upsell` importa `handle_friday_initiative_billing` e `friday_initiative_no_contact` importa `handle_friday_initiative_upsell`. Resultado: quando billing dispara, executa upsell. Quando upsell dispara, executa no_contact.

**Fix esperado:** Corrigir os imports para apontar ao handler correto de cada módulo.

### Acceptance Criteria
- [x] Import de `friday_initiative_upsell` aponta para o handler correto do módulo `friday_initiative_upsell.py`
- [x] Import de `friday_initiative_no_contact` aponta para o handler correto do módulo `friday_initiative_no_contact.py`
- [x] Nomes no REGISTRY dict são consistentes com o que cada handler realmente faz

---

## P0-2: Auth Middleware Fail-Open (Severidade: CRÍTICA)

**Arquivo:** `sparkle-runtime/runtime/middleware/auth.py` linhas 41-48
**Bug:** Se `RUNTIME_API_KEY` não está configurada, o middleware permite TODAS as requests sem autenticação. Deveria ser fail-closed.

**Fix esperado:** Se não houver API key configurada, rejeitar todas as requests protegidas com 503 (Service Unavailable — misconfigured).

### Acceptance Criteria
- [x] Se `RUNTIME_API_KEY` não está setada, requests protegidas retornam 503
- [x] Mensagem de erro clara: "API key not configured"
- [x] Log de warning mantido (uma vez) para diagnóstico
- [x] Health check (`/health`) continua acessível mesmo sem key

---

## P0-3: Asaas Webhook Sem Validação de Assinatura (Severidade: ALTA)

**Arquivo:** `sparkle-runtime/runtime/billing/router.py` linha 29
**Bug:** Qualquer um pode POST para `/billing/webhook/asaas` e criar/alterar pagamentos falsos. Não há validação de token/assinatura do Asaas.

**Fix esperado:** Validar `asaas-access-token` header (ou IP whitelist do Asaas) antes de processar o webhook.

### Acceptance Criteria
- [x] Webhook valida token de acesso do Asaas via header ou env var `ASAAS_WEBHOOK_TOKEN`
- [x] Requests sem token válido retornam 401
- [x] Log de tentativas inválidas para auditoria
- [x] Se `ASAAS_WEBHOOK_TOKEN` não configurado, webhook rejeita (fail-closed)

---

## P0-4: GETs Sensíveis Sem Autenticação (Severidade: ALTA)

**Arquivo:** `sparkle-runtime/runtime/middleware/auth.py` linha 53
**Bug:** Todos os GETs passam sem autenticação. Endpoints como `/cockpit/*`, `/billing/*`, `/brain/*`, `/observer/*` expõem dados sensíveis de negócio.

**Fix esperado:** Proteger GETs sensíveis. Manter apenas `/health`, `/docs`, `/openapi.json` como públicos.

### Acceptance Criteria
- [x] GETs em paths sensíveis (`/cockpit/*`, `/billing/*`, `/brain/*`, `/observer/*`, `/system/*`) exigem API key
- [x] GETs públicos mantidos: `/health`, `/docs`, `/openapi.json`, `/redoc`
- [x] Webhooks continuam isentos (já estão em EXEMPT_PATHS)

---

## P0-5: Rate Limit X-Forwarded-For Spoofable (Severidade: MÉDIA-ALTA)

**Arquivo:** `sparkle-runtime/runtime/middleware/rate_limit.py` linhas 139-149
**Bug:** `_get_client_ip()` confia cegamente no header `X-Forwarded-For`. Qualquer atacante pode enviar IPs falsos para contornar o rate limit.

**Fix esperado:** Usar o IP do socket (`request.client.host`) como padrão. Só confiar em `X-Forwarded-For` se vindo de IPs confiáveis (rede Docker/Traefik).

### Acceptance Criteria
- [x] `_get_client_ip()` só usa X-Forwarded-For se `request.client.host` está na lista de proxies confiáveis
- [x] Lista de proxies confiáveis inclui: `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`
- [x] Se o request não vem de proxy confiável, usa `request.client.host` diretamente

---

## File List

| Arquivo | Mudança |
|---------|---------|
| `sparkle-runtime/runtime/tasks/registry.py` | Fix imports trocados (P0-1) |
| `sparkle-runtime/runtime/middleware/auth.py` | Fail-closed + proteger GETs (P0-2, P0-4) |
| `sparkle-runtime/runtime/billing/router.py` | Validação webhook Asaas (P0-3) |
| `sparkle-runtime/runtime/middleware/rate_limit.py` | Trusted proxy check (P0-5) |
| `sparkle-runtime/runtime/config.py` | Adicionar `ASAAS_WEBHOOK_TOKEN` se necessário |

---

## Pipeline AIOS

1. **@architect (Aria)** — Spec aprovada ✅ (esta story)
2. **@dev** — Implementar os 5 fixes seguindo os acceptance criteria
3. **@qa** — Validar cada fix (testes manuais + edge cases)
4. **@devops** — Deploy em produção + health check
