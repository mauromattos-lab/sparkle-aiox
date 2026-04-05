# SEC-1 QA Validation Plan — P0 Security Fixes

**Status:** AGUARDANDO_IMPLEMENTACAO  
**Testado por:** @qa  
**Base URL:** `https://runtime.sparkleai.tech`  
**Pré-requisito:** @dev entregou os 5 fixes. Executar testes na ordem abaixo.

---

## Setup

```bash
# Variáveis para os testes — substituir pelos valores reais
GOOD_KEY="<RUNTIME_API_KEY real>"
BAD_KEY="wrong-key-12345"
BASE="https://runtime.sparkleai.tech"
ASAAS_TOKEN="<ASAAS_WEBHOOK_TOKEN configurado>"
```

---

## P0-1: Handler Swap no Registry

**Bug original:** `registry.py` importava `handle_friday_initiative_billing` do módulo `friday_initiative_upsell.py` e `handle_friday_initiative_upsell` do módulo `friday_initiative_no_contact.py`. Resultado: billing disparava upsell, upsell disparava no_contact.

### Happy path — verificar mapeamento correto

```bash
# 1. Inspecionar o registry após o fix (no VPS)
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "cd /opt/sparkle-runtime && python3 -c \"
from runtime.tasks.registry import REGISTRY
b = REGISTRY['friday_initiative_billing']
u = REGISTRY['friday_initiative_upsell']
print('billing module:', b.__module__)
print('upsell module:', u.__module__)
\""
```

**Esperado:**
- `billing module` deve conter `friday_initiative_upsell` (arquivo correto)
- `upsell module` deve conter `friday_initiative_no_contact` (arquivo correto)

**Importante:** os nomes das funções dentro dos arquivos também precisam bater. Verificar:
- `friday_initiative_upsell.py` → deve exportar `handle_friday_initiative_upsell` (não `billing`)
- `friday_initiative_no_contact.py` → deve exportar `handle_friday_initiative_no_contact` (não `upsell`)

Se @dev apenas trocou os imports sem renomear as funções dentro dos módulos, a lógica pode ainda estar errada. Confirmar que os nomes das funções fazem sentido com o conteúdo do arquivo.

### Edge cases

```bash
# 2. Dispatch explícito de friday_initiative_billing via API
curl -s -X POST $BASE/tasks \
  -H "X-API-Key: $GOOD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"friday_initiative_billing","agent_id":"friday","payload":{}}' \
  | jq '.task_type, .result.initiative_type // .result'
```

**Esperado:** resposta referencia billing/pagamento, não upsell

```bash
# 3. Dispatch de friday_initiative_upsell
curl -s -X POST $BASE/tasks \
  -H "X-API-Key: $GOOD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"friday_initiative_upsell","agent_id":"friday","payload":{}}' \
  | jq '.task_type, .result.initiative_type // .result'
```

**Esperado:** resposta referencia oportunidade de upsell (Zenya/tráfego), não billing

### Regressão

```bash
# 4. friday_initiative_risk não foi tocado — deve continuar funcionando
curl -s -X POST $BASE/tasks \
  -H "X-API-Key: $GOOD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"friday_initiative_risk","agent_id":"friday","payload":{}}' \
  | jq '.status // .error'
```

**Esperado:** responde sem erro (mesmo que sem dados)

```bash
# 5. task_type inexistente ainda retorna 404/erro limpo
curl -s -X POST $BASE/tasks \
  -H "X-API-Key: $GOOD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"nao_existe","agent_id":"friday","payload":{}}' \
  | jq '.detail // .error'
```

**Esperado:** erro claro, não 500

---

## P0-2: Auth Middleware Fail-Open

**Bug original:** Se `RUNTIME_API_KEY` não está setada, o middleware chama `call_next()` e deixa tudo passar. Deveria rejeitar com 503.

### Happy path — key configurada funciona normalmente

```bash
# 1. POST com key correta → aceita
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/tasks \
  -H "X-API-Key: $GOOD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"echo","agent_id":"test","payload":{"msg":"hi"}}'
```

**Esperado:** 200 (não 401, não 503)

### Edge cases

```bash
# 2. POST sem key → rejeita com 401
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type":"echo","agent_id":"test","payload":{}}'
```

**Esperado:** 401

```bash
# 3. POST com key errada → 401
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/tasks \
  -H "X-API-Key: $BAD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"echo","agent_id":"test","payload":{}}'
```

**Esperado:** 401

Para testar o comportamento quando a key NÃO está setada (503 fail-closed), testar em ambiente isolado ou temporariamente via VPS:

```bash
# 4. Simular RUNTIME_API_KEY ausente (em staging/VPS apenas)
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "RUNTIME_API_KEY='' python3 -c \"
import os; os.environ.pop('RUNTIME_API_KEY', None)
from runtime.config import get_settings
get_settings.cache_clear()
from runtime.middleware.auth import APIKeyMiddleware
print('fail-closed patch present:', True)
\""
```

Alternativa mais direta — checar o código fonte:

```bash
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "grep -n 'not api_key\|503\|api_key not configured' /opt/sparkle-runtime/runtime/middleware/auth.py"
```

**Esperado após fix:** bloco `if not api_key` deve retornar JSONResponse(503) em vez de `call_next(request)`

### Regressão

```bash
# 5. /health continua acessível sem key
curl -s -o /dev/null -w "%{http_code}" $BASE/health
```

**Esperado:** 200

```bash
# 6. /docs continua acessível sem key
curl -s -o /dev/null -w "%{http_code}" $BASE/docs
```

**Esperado:** 200

```bash
# 7. Webhooks ainda passam sem key
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/friday/webhook \
  -H "Content-Type: application/json" \
  -d '{"test":true}'
```

**Esperado:** qualquer código exceto 401/503 (pode ser 422 por payload inválido)

---

## P0-3: Asaas Webhook Sem Validação de Assinatura

**Bug original:** `POST /billing/webhook/asaas` aceita qualquer POST sem validar origem. Qualquer um pode forjar eventos de pagamento.

### Happy path — token válido é aceito

```bash
# 1. POST com token correto → processa (200 ou 202)
curl -s -X POST $BASE/billing/webhook/asaas \
  -H "Content-Type: application/json" \
  -H "asaas-access-token: $ASAAS_TOKEN" \
  -d '{
    "event": "PAYMENT_CREATED",
    "payment": {
      "id": "pay_qa_test_001",
      "value": 500,
      "status": "PENDING",
      "billingType": "PIX",
      "dueDate": "2026-04-30",
      "subscription": null
    }
  }' | jq '.status'
```

**Esperado:** `"ok"` (não 401)

### Edge cases

```bash
# 2. POST sem token → 401
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/billing/webhook/asaas \
  -H "Content-Type: application/json" \
  -d '{"event":"PAYMENT_RECEIVED","payment":{"id":"fake_pay_001"}}'
```

**Esperado:** 401

```bash
# 3. POST com token errado → 401
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/billing/webhook/asaas \
  -H "Content-Type: application/json" \
  -H "asaas-access-token: token-errado-atacante" \
  -d '{"event":"PAYMENT_RECEIVED","payment":{"id":"fake_pay_002"}}'
```

**Esperado:** 401

```bash
# 4. Verificar que tentativa inválida é logada (checar no VPS após teste 2/3)
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "journalctl -u sparkle-runtime --since '5 minutes ago' | grep -i 'webhook.*unauthorized\|invalid.*token\|billing.*401'"
```

**Esperado:** linha de log para cada tentativa rejeitada

### Comportamento quando ASAAS_WEBHOOK_TOKEN não está configurado

```bash
# 5. Sem a env var configurada, webhook deve rejeitar tudo (fail-closed)
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "grep -n 'ASAAS_WEBHOOK_TOKEN\|asaas_webhook_token' /opt/sparkle-runtime/runtime/config.py"
```

**Esperado:** campo presente em `config.py`

```bash
# 6. Verificar que o handler lê do settings, não hardcoded
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "grep -n 'asaas_webhook_token\|ASAAS_WEBHOOK_TOKEN\|fail.closed\|not.*token' /opt/sparkle-runtime/runtime/billing/router.py"
```

**Esperado:** referência ao `settings.asaas_webhook_token`

### Regressão

```bash
# 7. Outros endpoints de billing (GETs autenticados) não foram afetados
curl -s -o /dev/null -w "%{http_code}" $BASE/billing/subscriptions \
  -H "X-API-Key: $GOOD_KEY"
```

**Esperado:** 200 (não 500)

```bash
# 8. POST /billing/subscribe/<id> ainda funciona normalmente
curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE/billing/subscribe/client-nao-existe" \
  -H "X-API-Key: $GOOD_KEY"
```

**Esperado:** 404 (client not found), não 500

---

## P0-4: GETs Sensíveis Sem Autenticação

**Bug original:** `auth.py` deixava todos os GETs passarem sem autenticação. `/cockpit/*`, `/billing/*`, `/brain/*`, `/observer/*`, `/system/*` expostos publicamente.

### Happy path — GETs sensíveis com key válida

```bash
# 1. GET /billing/subscriptions com key → 200
curl -s -o /dev/null -w "%{http_code}" $BASE/billing/subscriptions \
  -H "X-API-Key: $GOOD_KEY"
```

**Esperado:** 200

```bash
# 2. GET /system/state com key → 200
curl -s -o /dev/null -w "%{http_code}" "$BASE/system/state" \
  -H "X-API-Key: $GOOD_KEY"
```

**Esperado:** 200

### Edge cases — GETs sensíveis SEM key agora rejeitados

```bash
# 3. GET /billing/subscriptions sem key → 401
curl -s -o /dev/null -w "%{http_code}" $BASE/billing/subscriptions
```

**Esperado:** 401

```bash
# 4. GET /billing/client/<uuid> sem key → 401
curl -s -o /dev/null -w "%{http_code}" \
  "$BASE/billing/client/00000000-0000-0000-0000-000000000000"
```

**Esperado:** 401

```bash
# 5. GET /brain/query ou /brain/* sem key → 401
curl -s -o /dev/null -w "%{http_code}" \
  "$BASE/brain/query?q=test"
```

**Esperado:** 401

```bash
# 6. GET /observer/* sem key → 401
curl -s -o /dev/null -w "%{http_code}" $BASE/observer/gaps
```

**Esperado:** 401

```bash
# 7. GET /system/state sem key → 401
curl -s -o /dev/null -w "%{http_code}" "$BASE/system/state"
```

**Esperado:** 401

### Regressão — paths públicos continuam abertos

```bash
# 8. /health sem key → 200
curl -s -o /dev/null -w "%{http_code}" $BASE/health
```

**Esperado:** 200

```bash
# 9. /docs sem key → 200
curl -s -o /dev/null -w "%{http_code}" $BASE/docs
```

**Esperado:** 200

```bash
# 10. /openapi.json sem key → 200
curl -s -o /dev/null -w "%{http_code}" $BASE/openapi.json
```

**Esperado:** 200

```bash
# 11. /redoc sem key → 200
curl -s -o /dev/null -w "%{http_code}" $BASE/redoc
```

**Esperado:** 200

```bash
# 12. Webhooks (POST) continuam isentos
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/friday/webhook \
  -H "Content-Type: application/json" \
  -d '{"test":true}'
```

**Esperado:** não 401 (pode ser 422)

```bash
# 13. Verificar que PROTECTED_METHODS agora inclui GET nos paths sensíveis
# (checar implementação no VPS)
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "grep -n 'SENSITIVE\|sensitive_paths\|GET.*auth\|protected.*get\|PROTECTED_METHODS' \
  /opt/sparkle-runtime/runtime/middleware/auth.py"
```

**Esperado:** lógica de proteção de GETs visível no código

---

## P0-5: Rate Limit X-Forwarded-For Spoofable

**Bug original:** `_get_client_ip()` confiava cegamente em `X-Forwarded-For`. Atacante podia forjar IPs para escapar do rate limit.

### Happy path — IP real (sem X-Forwarded-For)

```bash
# 1. Request normal sem header forjado — funciona normalmente
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/tasks \
  -H "X-API-Key: $GOOD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"echo","agent_id":"test","payload":{"msg":"hi"}}'
```

**Esperado:** 200

### Edge cases — header forjado não bypassa rate limit

```bash
# 2. Forjar X-Forwarded-For com IP externo — deve usar socket IP, não o header
# Enviar 15 requests com X-Forwarded-For diferente (simula bypass)
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/tasks \
    -H "X-API-Key: $GOOD_KEY" \
    -H "X-Forwarded-For: 1.2.3.$i" \
    -H "Content-Type: application/json" \
    -d '{"task_type":"echo","agent_id":"test","payload":{"msg":"hi"}}'
done
```

**Esperado após fix:** após atingir o limite (120/min global), retornar 429 — mesmo com IPs diferentes no header. Se o bypass ainda funcionar, todos os 15 retornarão 200 indefinidamente.

```bash
# 3. Checar implementação — trusted proxies presentes no código
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "grep -n 'trusted\|TRUSTED\|127.0.0.1\|10\.0\.0\|172\.16\|proxy' \
  /opt/sparkle-runtime/runtime/middleware/rate_limit.py"
```

**Esperado:** lista de TRUSTED_PROXIES com `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`

```bash
# 4. Checar que _get_client_ip usa socket IP como padrão
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "grep -A 10 'def _get_client_ip' /opt/sparkle-runtime/runtime/middleware/rate_limit.py"
```

**Esperado:** lógica que primeiro verifica se `request.client.host` é proxy confiável antes de honrar `X-Forwarded-For`

### Teste de rate limit legitimo (Traefik/Nginx passando X-Forwarded-For)

```bash
# 5. Verificar que requests vindas de proxy interno (127.0.0.1) ainda usam X-Forwarded-For
# Simulado no VPS — request vinda do próprio servidor via curl local
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88 \
  "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/tasks \
  -H 'X-API-Key: $GOOD_KEY' \
  -H 'X-Forwarded-For: 200.100.50.25' \
  -H 'Content-Type: application/json' \
  -d '{\"task_type\":\"echo\",\"agent_id\":\"test\",\"payload\":{}}'"
```

**Esperado:** 200 (127.0.0.1 é proxy confiável → honra X-Forwarded-For → usa 200.100.50.25 como IP do cliente)

### Regressão

```bash
# 6. Rate limit normal continua funcionando (não quebrou proteção)
# Enviar 125 requests rápidos sem forjar header — o 121º deve ser 429
for i in $(seq 1 125); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" $BASE/health)
  if [ "$CODE" = "429" ]; then echo "429 recebido na request $i"; break; fi
done
```

**Nota:** `/health` é exempt — usar outro endpoint não-exempt se necessário.

---

## Checklist de Aprovação (sign-off @qa)

| Fix | Happy Path | Edge Cases | Regressão | Status |
|-----|-----------|------------|-----------|--------|
| P0-1 Handler Swap | [ ] | [ ] | [ ] | PENDENTE |
| P0-2 Fail-Open Auth | [ ] | [ ] | [ ] | PENDENTE |
| P0-3 Asaas Webhook | [ ] | [ ] | [ ] | PENDENTE |
| P0-4 GETs Sensíveis | [ ] | [ ] | [ ] | PENDENTE |
| P0-5 Rate Limit Spoof | [ ] | [ ] | [ ] | PENDENTE |

**Regra:** todos os campos marcados [x] antes do handoff para @devops.  
Se qualquer teste falhar → abrir bug blocker, bloquear deploy.

---

## Handoff

- Aprovado: @devops para deploy em produção
- Bloqueado: reportar para @dev com número do P0 e output exato do curl que falhou
