---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.9
title: "Portal — Calendar View (Briefing e Calendário de Produção)"
status: Done
priority: P1
executor: "@dev (Portal Next.js)"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.6]
unblocks: [CONTENT-1.11]
estimated_effort: 4-5h de agente (@dev)
blocker_soft: "QA-2 (pilares de conteúdo) e QA-4 (horários) — preencher placeholders após Mauro responder"
---

# Story 1.9 — Portal — Calendar View (Briefing e Calendário de Produção)

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 10 de 13 (paralelo com 1.7 e 1.8)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR6
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como Mauro,
> quero criar briefs de conteúdo diretamente no Portal e visualizar o calendário de produção com o status de cada peça,
> para que eu planeje e acompanhe o pipeline de 5 peças/dia sem usar planilhas ou ferramentas externas.

---

## Contexto Técnico

**Estado atual:** Nenhuma view de calendário ou briefing no Portal.

**Estado alvo:** `/content/` — dashboard principal do domínio com: calendário semanal mostrando peças por dia + status, formulário de criação de brief, fila de produção em andamento.

**Nota sobre QA-2 e QA-4:** Os pilares/temas de conteúdo e horários de publicação ainda precisam ser definidos por Mauro (Open Questions do Discovery). Esta story implementa a interface; os valores padrão serão configurados depois. @dev deixa campos `theme` e `scheduled_at` como livres — sem validação de pilares por ora.

---

## Acceptance Criteria

- [x] **AC1** — `/content/` exibe calendário semanal (7 dias) com peças agendadas ou em produção por data
- [x] **AC2** — Cada dia no calendário mostra: quantas peças estão em `published`, `approved`, `pending_approval`, `assembly_done`, em produção
- [x] **AC3** — Formulário de criação de brief: campos `theme` (texto livre), `mood` (dropdown: alegre/inspirador/educativo/emocional), `style` (cinematic / influencer_natural), `target_date`
- [x] **AC4** — Submissão do formulário chama `POST /content/briefs` e adiciona peça ao calendário com `status = 'briefed'`
- [x] **AC5** — Lista "Em produção" abaixo do calendário mostra todas as peças com status `image_generating`, `video_generating`, `assembly_pending`, etc. com indicador de progresso visual
- [x] **AC6** — Limite visual: quando há 5 peças em produção, formulário de brief exibe aviso "Pipeline cheio — aguarde uma peça concluir antes de criar nova"
- [x] **AC7** — Click em qualquer peça do calendário abre detail panel com: status atual, pipeline_log (timeline), assets (imagem/vídeo/áudio se disponíveis)
- [x] **AC8** — Link direto para `/content/queue` quando há peças `pending_approval` — badge com contador

---

## Dev Notes

### Layout da página
```tsx
// /content/page.tsx
export default function ContentDashboard() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1>Produção de Conteúdo</h1>
        {pendingCount > 0 && (
          <Link href="/content/queue">
            <Badge>{pendingCount} aguardando aprovação</Badge>
          </Link>
        )}
      </div>
      
      <WeeklyCalendar pieces={pieces} />
      
      <div className="grid grid-cols-2 gap-6">
        <BriefForm onSubmit={createBrief} disabled={inProductionCount >= 5} />
        <ProductionQueue pieces={inProduction} />
      </div>
    </div>
  )
}
```

### Opções de mood (placeholders até QA-2 ser respondida)
```tsx
const MOOD_OPTIONS = [
  { value: 'inspirador', label: 'Inspirador' },
  { value: 'educativo', label: 'Educativo' },
  { value: 'alegre', label: 'Alegre' },
  { value: 'reflexivo', label: 'Reflexivo' },
  { value: 'emocional', label: 'Emocional' },
]
// NOTA: adicionar pilares específicos da Zenya após Mauro responder QA-2
```

### Status colors para pipeline visual
```tsx
const STATUS_COLORS = {
  briefed: 'gray',
  image_generating: 'blue',
  image_done: 'blue',
  video_generating: 'purple',
  video_done: 'purple',
  assembly_pending: 'orange',
  assembly_done: 'orange',
  pending_approval: 'yellow',
  approved: 'green',
  published: 'green',
  rejected: 'red',
  image_failed: 'red',
  video_failed: 'red',
}
```

---

## Integration Verifications

- [x] `/content/` carrega e exibe calendário semanal com peças reais
- [x] Formulário de brief cria peça e aparece na lista em produção
- [x] Limite de 5 peças exibe aviso correto
- [x] Click em peça abre detail com pipeline_log
- [x] Badge de aprovação pendente aparece e linka para `/content/queue`

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `portal/app/hq/content/page.tsx` | Criado | Dashboard principal — WeeklyCalendar + BriefForm + ProductionQueue + PieceDetailPanel inline |
| `portal/app/api/hq/content/briefs/route.ts` | Criado | Proxy GET+POST /content/briefs |
| `portal/app/api/hq/content/pieces/route.ts` | Criado | Proxy GET /content/pieces (lista todas as peças para o calendário) |

---

## Dev Agent Record

**Agent Model:** claude-sonnet-4-6
**Completed:** 2026-04-07
**Completion Notes:** Todos os 8 ACs implementados. Componentes inline no page.tsx: WeeklyCalendar (navegação semana anterior/próxima), BriefForm (tema + mood + style + data), ProductionQueue (barra de progresso visual por etapa do pipeline), PieceDetailPanel (timeline de pipeline_log, links para assets). AC6: aviso "Pipeline cheio" quando ≥5 peças em IN_PRODUCTION_STATUSES. AC8: badge amarelo linkando para /hq/content/queue. Build passou sem erros.
**Change Log:**
- Criado `portal/app/hq/content/page.tsx`
- Criado `portal/app/api/hq/content/briefs/route.ts`
- Criado `portal/app/api/hq/content/pieces/route.ts`

---

## QA Results

**Revisor:** @qa (Quinn) — 2026-04-07
**Resultado:** PASS com CONCERNS ⚠️

| AC | Status | Nota |
|----|--------|------|
| AC1 | ✅ | Calendário semanal 7 dias com peças por data |
| AC2 | ✅ | Cada dia exibe contagem por status |
| AC3 | ✅ | BriefForm com theme/mood/style/target_date |
| AC4 | ✅ | POST /content/briefs adiciona peça ao calendário com status='briefed' |
| AC5 | ✅ | Lista "Em produção" com progress visual por etapa |
| AC6 | ✅ | Aviso "Pipeline cheio" quando ≥5 peças em IN_PRODUCTION_STATUSES |
| AC7 | ✅ | Click em peça abre PieceDetailPanel com pipeline_log timeline |
| AC8 | ✅ | Badge linkando para /hq/content/queue quando há pending_approval |

**Concerns:**
- MÉDIO: `STATUS_COLORS` no page.tsx inclui `assembly_pending` e `assembly_done` — status removidos do MVP v1.1. São dead code inofensivo mas pode confundir em manutenção futura.
- BAIXO: Pilares de conteúdo (MOOD_OPTIONS) são placeholders — pendente resposta de Mauro à QA-2. Documentado na story como blocker_soft.
