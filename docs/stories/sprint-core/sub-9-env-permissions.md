# Story SUB-9 — .env Permissions Hardening

**Sprint:** Plano Ponte — Semana 2
**Agente responsável:** @devops
**Esforço estimado:** 30 min
**Prioridade:** P1 — Segurança
**Status:** AGUARDANDO_QA

---

## Contexto

A auditoria brownfield (Gage P0-7) marcou ".env permissions 644→600" como FEITO.
O QA reverteu: o `.env` em `/opt/sparkle-aiox/.env` ainda está **644** (world-readable).

### Estado verificado via SSH (2026-04-05)

| Arquivo | Permissão atual | Status |
|---|---|---|
| `/opt/sparkle-aiox/sparkle-runtime/.env` | `600 root:root` | OK |
| `/opt/sparkle-aiox/.env` | `644 root:root` | VULNERAVEL |

O `.env` raiz (`/opt/sparkle-aiox/.env`) não é lido diretamente pelos services systemd
(ambos apontam para `/opt/sparkle-aiox/sparkle-runtime/.env`), mas está no diretório
raiz do repositório e é world-readable — qualquer usuário do sistema pode ler
todas as credenciais (Supabase, Z-API, Anthropic, etc.).

O deploy script (`.github/workflows/deploy-runtime.yml`) executa `git pull origin main`
mas não reaplica permissões após o pull, criando risco de regressão a cada deploy.

---

## Scope

- Corrigir `/opt/sparkle-aiox/.env` para `600 root:root`
- Garantir que o deploy script reaplique `chmod 600` após cada `git pull`
- Confirmar que nenhum outro `.env` no filesystem está com permissão permissiva

---

## Acceptance Criteria

- [ ] **AC-1:** `stat -c '%a' /opt/sparkle-aiox/.env` retorna `600`
- [ ] **AC-2:** `stat -c '%a' /opt/sparkle-aiox/sparkle-runtime/.env` retorna `600` (mantido)
- [ ] **AC-3:** `find /opt/sparkle-aiox -name '.env' -not -perm 600` retorna vazio
- [ ] **AC-4:** O step de deploy em `.github/workflows/deploy-runtime.yml` inclui, após o `git pull`, o bloco:
  ```bash
  echo "=== [2.5/5] Hardening .env permissions ==="
  find "$DEPLOY_DIR" -name '.env' -exec chmod 600 {} \;
  ```
- [ ] **AC-5:** Após o próximo deploy real, o AC-3 continua verde (sem regressão)
- [ ] **AC-6:** Os serviços `sparkle-runtime` e `sparkle-arq` continuam healthy após a alteração (`/health` retorna HTTP 200`)

---

## Tarefas para @devops

```
[x] 1. SSH na VPS: chmod 600 /opt/sparkle-aiox/.env
[x] 2. Verificar todos os .env no filesystem: find /opt/sparkle-aiox -name '.env' -exec stat -c '%a %n' {} \;
[x] 3. Editar .github/workflows/deploy-runtime.yml — adicionar step de chmod após git pull (ver AC-4)
[x] 4. Confirmar que services não foram afetados: systemctl status sparkle-runtime sparkle-arq
[x] 5. Commit + push do workflow atualizado
[x] 6. Rodar AC-3 novamente para confirmar estado limpo
```

---

## Riscos

- **Nenhum downtime esperado** — chmod em arquivo não reinicia serviço
- O systemd já leu o `.env` no boot; a permissão não afeta o processo em execução
- O único risco é o AC-6 (health check pós-alteração), que deve ser trivialmente verde

---

## Handoff

Após conclusão: reportar via `POST /system/state` com `sprint_item: "SUB-9"` e `status: "funcional"`.
Próximo: @qa valida AC-1 a AC-6 antes de fechar.

---

## Arquivos que serão modificados

| Arquivo | Tipo de mudança |
|---|---|
| `/opt/sparkle-aiox/.env` (VPS) | chmod 600 — sem edição de conteúdo |
| `.github/workflows/deploy-runtime.yml` | Adicionar step de hardening pós-git-pull |
