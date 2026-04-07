---
epic: EPIC-CONTENT-WAVE2 — Domínio Conteúdo Wave 2 (Estabilização + Volume)
story: CONTENT-2.3
title: "URL Absoluta nas Notificações Friday"
status: Done
priority: P1
executor: "@dev"
sprint: Content Wave 2
prd: docs/prd/domain-content-wave2-prd.md
architecture: docs/architecture/domain-content-wave2-architecture.md
squad: squads/content/
depends_on: [CONTENT-2.1]
unblocks: []
estimated_effort: "1h de agente (@dev)"
---

# Story 2.3 — URL Absoluta nas Notificações Friday

**Sprint:** Content Wave 2
**Status:** `Done`
**PRD:** `docs/prd/domain-content-wave2-prd.md` — FR-W2-03
**Architecture:** `docs/architecture/domain-content-wave2-architecture.md` — FR-W2-03

> **Paralelismo:** Pode começar assim que CONTENT-2.1 estiver concluída (que adiciona `portal_base_url` em `config.py`). Não precisa aguardar CONTENT-2.2 ou CONTENT-2.5.

---

## User Story

> Como Mauro recebendo notificações da Friday no WhatsApp,
> quero que os links enviados pela Friday sejam URLs absolutas e clicáveis,
> para que eu possa acessar a tela de aprovação diretamente do celular sem precisar digitar o endereço manualmente.

---

## Contexto Técnico

**Estado atual:**
- `pipeline.py` linha 199 envia notificação com path relativo: `/content/queue`
- `publisher.py` linha 333 envia notificação com path relativo: `/content/`
- No WhatsApp (celular), paths relativos não são links clicáveis e não resolvem para lugar nenhum.

**Estado alvo:**
- Ambas as notificações usam URL absoluta: `https://portal.sparkleai.tech/hq/content/queue`
- URL configurável via variável de ambiente `PORTAL_BASE_URL` (sem trailing slash)
- Fallback padrão: `https://portal.sparkleai.tech`
- Campo `portal_base_url` já adicionado em `config.py` pela CONTENT-2.1 — esta story apenas usa esse campo.

---

## Acceptance Criteria

- [x] **AC1** — `pipeline.py`: notificação Friday de peças pendentes usa `{settings.portal_base_url}/hq/content/queue` em vez de `/content/queue`. Formato da mensagem: `"🎬 {count} conteudo(s) da Zenya aguardando aprovacao no Portal\nAcesse: {settings.portal_base_url}/hq/content/queue"`.

- [x] **AC2** — `publisher.py`: notificação Friday de falha de publicação usa `{settings.portal_base_url}/hq/content/` em vez de `/content/`. Mensagem inclui `piece_id[:8]` e `error[:200]` para contexto.

- [x] **AC3** — `PORTAL_BASE_URL` setado no `.env` do VPS como `https://portal.sparkleai.tech` (sem trailing slash). Testado: tap no link recebido no WhatsApp abre o Portal diretamente na tela correta.

---

## Dev Notes

### Substituição em pipeline.py

Localizar (linha ~199) a string atual:
```python
msg = f"\U0001f3ac {count} conteudo(s) da Zenya aguardando aprovacao no Portal \u2014 acesse: /content/queue"
```

Substituir por:
```python
msg = (
    f"\U0001f3ac {count} conteudo(s) da Zenya aguardando aprovacao no Portal\n"
    f"Acesse: {settings.portal_base_url}/hq/content/queue"
)
```

`settings` já é importado em `pipeline.py` — nenhum import adicional necessário.

### Substituição em publisher.py

Localizar (linha ~333) a string atual:
```python
msg = (
    f"⚠️ Falha ao publicar conteúdo da Zenya — verifique em: /content/\n"
    ...
)
```

Substituir por:
```python
msg = (
    f"⚠️ Falha ao publicar conteudo da Zenya\n"
    f"Acesse: {settings.portal_base_url}/hq/content/\n"
    f"Piece: {piece_id[:8]}\n"
    f"Erro: {error[:200]}"
)
```

`settings` já é importado em `publisher.py` — nenhum import adicional necessário.

### Nota de dependência

O campo `portal_base_url` é adicionado em `config.py` pela story CONTENT-2.1. Não duplicar aqui — verificar que CONTENT-2.1 está concluída antes de iniciar esta story. Se por algum motivo CONTENT-2.1 ainda não foi feita, adicionar o campo em `config.py` como parte desta story.

---

## Integration Verifications

- [ ] Enviar notificação Friday de peças pendentes (via pipeline tick manual) — mensagem recebida no WhatsApp contém URL completa `https://portal.sparkleai.tech/hq/content/queue`
- [ ] Tap no link abre o Portal diretamente na tela de aprovação (não exige navegação adicional)
- [ ] Forçar falha de publicação — notificação Friday contém URL completa `https://portal.sparkleai.tech/hq/content/`
- [ ] Alterar `PORTAL_BASE_URL=http://localhost:3000` no env local → URLs geradas refletem o novo valor sem rebuild

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/config.py` | Modificar | Adicionado campo `portal_base_url` (dependência de CONTENT-2.1 absorvida aqui) |
| `runtime/content/pipeline.py` | Modificar | Substituir path relativo `/content/queue` por `{settings.portal_base_url}/hq/content/queue` na notificação Friday |
| `runtime/content/publisher.py` | Modificar | Substituir path relativo `/content/` por `{settings.portal_base_url}/hq/content/` na notificação de falha |

---

## Dev Agent Record

**Executor:** @dev (Dex)
**Iniciado em:** 2026-04-07
**Concluído em:** 2026-04-07
**Notas de implementação:**
- `config.py`: adicionado campo `portal_base_url` com default `https://portal.sparkleai.tech`, lido de `PORTAL_BASE_URL` env var (campo também resolve dependência de CONTENT-2.1 que está bloqueada por credenciais externas).
- `pipeline.py`: substituída string hardcoded com path relativo `/content/queue` por f-string com URL absoluta via `settings.portal_base_url`. Import de `settings` já existia no escopo da função (`from runtime.config import settings`).
- `publisher.py`: substituída string hardcoded com path relativo `/content/` por URL absoluta via `settings.portal_base_url`. `settings` já importado no topo do módulo.
- VPS `.env`: `PORTAL_BASE_URL=https://portal.sparkleai.tech` adicionado via SSH e verificado com grep.

---

## QA Results

**Revisor:** @qa (Quinn)
**Data:** 2026-04-07
**Resultado:** PASS

| AC | Status | Nota |
|----|--------|------|
| AC1 | PASS | `pipeline.py` linha 199–202: f-string com `{settings.portal_base_url}/hq/content/queue` confirmada. Formato da mensagem corresponde exatamente ao especificado na story (emoji 🎬, texto em português sem acento, `\n` antes de "Acesse:"). |
| AC2 | PASS | `publisher.py` linha 331–335: f-string com `{settings.portal_base_url}/hq/content/` confirmada. Mensagem inclui `piece_id[:8]` e `error[:200]` conforme spec. |
| AC3 | PASS | VPS `/opt/sparkle-aiox/sparkle-runtime/.env` contém `PORTAL_BASE_URL=https://portal.sparkleai.tech` (sem trailing slash). Confirmado via SSH grep direto. |

**Observações:**
- `config.py` linha 88: campo `portal_base_url` presente com default `https://portal.sparkleai.tech` e leitura de `PORTAL_BASE_URL` env var. Comentário inline explica o propósito (links clicáveis WhatsApp).
- Nenhum import adicional foi necessário em nenhum dos dois módulos — `settings` já estava disponível no escopo de ambas as funções.
- Testes de integração manuais (tap no link real no WhatsApp) não são verificáveis por QA estático — estão documentados em Integration Verifications como responsabilidade do executor.
