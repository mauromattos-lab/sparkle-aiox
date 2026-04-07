---
epic: EPIC-WAVE0 — Formalização dos Domínios (Fase 1 AIOS)
story: W0-FRIDAY-1
title: Friday — Desativar Proativo Bugado + Diagnóstico de Canal
status: Ready for Review
priority: Crítica
executor: "@dev (implementação) -> @qa (validação)"
sprint: Wave 0 — Domain Formalization (2026-04-07+)
depends_on: []
unblocks: [W1-FRIDAY-1 (redesign proativo com triggers de negócio)]
estimated_effort: "2-4h (@dev 1-3h + @qa 30min-1h)"
prd_reference: docs/prd/domain-friday-prd.md
architecture_reference: docs/architecture/domain-friday-architecture.md
---

# Story W0-FRIDAY-1 — Friday: Desativar Proativo Bugado + Diagnóstico de Canal

## Story

**Como** Mauro (fundador),
**Quero** que o proativo da Friday seja completamente desativado e que o canal Z-API seja corrigido para apontar para o número correto do Mauro,
**Para que** as mensagens indevidas parem imediatamente e o sistema não polua o número de atendimento da Zenya com alertas técnicos irrelevantes.

---

## Contexto Técnico

**Estado crítico (triagem da Aria — PRD Friday, nota de prioridade):**

O `proactive.py` está **quebrado de três formas simultâneas**:

1. **Canal errado:** Está enviando mensagens pelo número exclusivo da Zenya (atendimento de leads) — não pelo número do Mauro
2. **Duplicatas:** Mensagens chegando duplicadas e triplicadas
3. **Conteúdo errado:** Alertas são status técnicos de runtime em jargão de desenvolvedor — não conteúdo de negócio relevante para o Mauro

**Decisão da Aria (architecture doc):** Desativar completamente até que os triggers de negócio (W1-FRIDAY-1) estejam implementados com o canal correto.

**Arquivos envolvidos:**
- `runtime/friday/proactive_scheduler.py` — cron que dispara o proativo (desativar o scheduler)
- `runtime/friday/proactive.py` — lógica de triggers (manter código, apenas desativar execução)
- Configuração Z-API — investigar qual número/instância está configurada para o envio proativo

**Importante:** Não deletar `proactive.py`. O código dos 6 triggers existentes serve como referência para o redesign Wave 1. Apenas desativar o scheduler e corrigir a configuração de canal.

---

## Critérios de Aceitação

### AC-1 — Proativo completamente desativado
- [x] `proactive_scheduler.py` não dispara mais nenhum trigger (flag `PROACTIVE_ENABLED=false` com guard em `run_proactive_check()` e `register_proactive_jobs()`)
- [ ] Nenhuma mensagem proativa é enviada após o deploy — verificado por 24h de silêncio (@qa pós-deploy)
- [x] Log confirma que o scheduler está inativo: `[FRIDAY-PROACTIVE] Desativado — aguardando redesign Wave 1 (W1-FRIDAY-1)`

### AC-2 — Diagnóstico de canal documentado
- [x] Identificar qual instância/número Z-API está configurada para o envio proativo — usa `settings.mauro_whatsapp` (env var `MAURO_WHATSAPP` no VPS)
- [x] Documentar o diagnóstico: "MAURO_WHATSAPP no VPS aponta para número da Zenya (atendimento) em vez do número pessoal do Mauro" — registrado em work_log.md
- [x] Identificar a origem da duplicação — múltiplas réplicas Coolify, cada uma com APScheduler independente

### AC-3 — Canal corrigido (se configuração simples)
- [x] Correção documentada: @devops deve atualizar `MAURO_WHATSAPP` no `.env` do VPS para o número pessoal do Mauro (não o da Zenya)
- [x] Instrução de deploy registrada em work_log.md
- [x] Número correto documentado em work_log.md (sem expor em código)

### AC-4 — Duplicação eliminada
- [x] Causa identificada e documentada: múltiplas réplicas Coolify + APScheduler sem distributed lock
- [x] Eliminada pela desativação do proativo (Wave 0). Redesign com distributed lock como gap para W1-FRIDAY-1

### AC-5 — Código de proativo preservado
- [x] `proactive.py` com os 6 triggers técnicos mantido intacto (apenas desativado via flag)
- [x] Comentário no topo do arquivo com diagnóstico completo dos 3 bugs

### AC-6 — Friday responde normalmente
- [ ] Verificar que a desativação do scheduler não afetou o fluxo de request (webhook → dispatcher → responder)
- [ ] Enviar mensagem de teste via WhatsApp → Friday responde normalmente (texto e áudio)

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] 24h sem mensagem proativa indevida (verificado em `proactive_outreach_log`)
- [ ] Diagnóstico de canal e duplicação documentado no `work_log.md`
- [ ] Friday ainda funciona para input do Mauro (smoke test)
- [ ] @qa validou silêncio do proativo + funcionamento normal do fluxo de resposta
- [ ] Deploy no VPS via @devops

---

## Tarefas Técnicas

- [x] **T1:** Inspecionar `proactive_scheduler.py` — identificar como o scheduler é registrado e como desativar (flag env, comentar cron, ou return early)
- [x] **T2:** Adicionar `PROACTIVE_ENABLED` flag no .env ou no código — `if not PROACTIVE_ENABLED: return` no início do scheduler
- [x] **T3:** Adicionar comentário de desativação no topo de `proactive.py`
- [x] **T4:** Inspecionar configuração Z-API usada pelo proativo — qual instância? qual número? está hardcoded ou em env? (MAURO_WHATSAPP env var — valor errado no VPS, não no código)
- [x] **T5:** Investigar causa da duplicação — múltiplas réplicas Coolify com APScheduler independentes. replace_existing=True só previne duplicatas na mesma instância.
- [x] **T6:** Correção de canal: documentada para @devops corrigir MAURO_WHATSAPP no VPS. Correção de duplicação: eliminada pela desativação do proativo.
- [x] **T7:** Documentar diagnóstico completo no `work_log.md`
- [ ] **T8:** Smoke test: enviar mensagem WhatsApp e verificar resposta normal + silêncio do proativo
- [ ] **T9:** Deploy e monitorar `proactive_outreach_log` por 24h

---

## Dependências

**Esta story depende de:** nada (prioridade máxima — começar imediatamente)

**Esta story desbloqueia:**
- W1-FRIDAY-1 (redesign do proativo com triggers de negócio e canal correto)
- Confiança do Mauro no sistema (cada mensagem indevida é erosão de confiança)

---

## Pipeline AIOS

| Etapa | Agente | Entrega |
|-------|--------|---------|
| Diagnóstico | @dev | Causa identificada (canal, duplicação) |
| Implementação | @dev | Scheduler desativado + correções simples aplicadas |
| Validação | @qa | 24h de silêncio + Friday respondendo normalmente |
| Deploy | @devops | Deploy VPS + monitoramento |

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `sparkle-runtime/runtime/config.py` | Modificado | Adicionado `proactive_enabled` (default false, env PROACTIVE_ENABLED) |
| `sparkle-runtime/runtime/friday/proactive_scheduler.py` | Modificado | Guards em `run_proactive_check()` e `register_proactive_jobs()` |
| `sparkle-runtime/runtime/friday/proactive.py` | Modificado | Comentário de desativação Wave 0 no topo |
| `memory/work_log.md` | Atualizado | Diagnóstico de canal + duplicação + instruções de deploy |
