# PLANO ATUAL — Sparkle AIOX
> Orion lê este arquivo no início de TODA sessão antes de qualquer ação.
> Última atualização: 2026-03-31

---

## PLANO VIGENTE (NÃO SUBSTITUIR SEM ATUALIZAR AQUI)

| Documento | Papel |
|-----------|-------|
| `docs/strategy/plano-mestre-sparkle-2026.md` | Estratégia — 3 fases (Abr / Mai-Jun / Jul-Dez 2026) |
| `docs/architecture/dev-vision-marco0.md` | Marco 0 técnico — FastAPI Runtime |
| `docs/architecture/aria-architectural-evaluation.md` | 6 decisões arquiteturais (todas implementadas) |
| `docs/architecture/sparkle-brain-mechanism.md` | Mecanismo técnico do Sparkle Brain |
| `docs/architecture/sparkle-os-project.md` | Arquitetura de longo prazo do Runtime |

**NÃO usar como plano principal:** `docs/architecture/aios-v2/` (n8n AIOS v2 — infraestrutura de suporte, não o foco de desenvolvimento)

---

## STATUS MARCO 0 (atualizado 2026-03-31)

| Item | Status |
|------|--------|
| `sparkle-runtime/` — código FastAPI | ✅ EXISTE E RODANDO (smoke test aprovado) |
| Migration `001_initial.sql` no Supabase | ✅ APLICADA (agents, runtime_tasks, llm_cost_log, brain_*) |
| BUG-01 e BUG-02 do QA report | ✅ JÁ CORRIGIDOS pelo Dex |
| `/health` — todos checks verdes | ✅ supabase, zapi, groq, anthropic |
| `echo` e `status_report` intents | ✅ FUNCIONANDO |
| Deploy VPS (24/7) | ❌ PENDENTE |
| Friday v1.1 — audio via Z-API webhook | ❌ PENDENTE (transcriber existe, falta teste E2E) |
| Zenya Confeitaria go-live | ❌ BLOQUEADO (BLOCK-01: Z-API pendente do Mauro) |
| Dashboard mínimo (3 telas) | ❌ PENDENTE |

---

## PRIORIDADE DE TRABALHO

1. **Plano-mestre Fase 1** é a prioridade padrão
2. **Clientes** entram como interrupção quando Mauro traz algo específico
3. **AIOS v2 / n8n** só recebe trabalho se diretamente necessário para cliente existente

---

## PRÓXIMOS PASSOS DESBLOQUEADOS (sem depender do Mauro)

1. Deploy Runtime na VPS (Railway/Render) — Runtime rodando 24/7
2. Testar Friday audio pipeline end-to-end (webhook Z-API → Whisper → resposta)
3. Dashboard mínimo — popular portal Next.js com queries do Runtime + Supabase

## PRÓXIMOS PASSOS QUE DEPENDEM DO MAURO

- BLOCK-01: Z-API Confeitaria → Chatwoot inbox → Zenya go-live
- BLOCK-02: Resposta do Douglas (Ensinaja)
- BLOCK-03: API key Loja Integrada (Julia / Fun Personalize)
- BLOCK-04: Redirect Z-API Friday para Runtime webhook
- BLOCK-05: Vincular ad account Gabriela + criativos
- BLOCK-06: WhatsApp Vitalis (João)

---

## REGRA ANTI-DESVIO

Se Orion começar uma sessão e a conversa anterior tinha contexto de AIOS v2 ou outro plano:
**PARAR. Ler este arquivo. Retomar pelo próximo item desbloqueado acima.**
