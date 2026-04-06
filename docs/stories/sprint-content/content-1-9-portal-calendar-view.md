---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.9
title: "Portal — Calendar View (Briefing e Calendário de Produção)"
status: TODO
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

- [ ] **AC1** — `/content/` exibe calendário semanal (7 dias) com peças agendadas ou em produção por data
- [ ] **AC2** — Cada dia no calendário mostra: quantas peças estão em `published`, `approved`, `pending_approval`, `assembly_done`, em produção
- [ ] **AC3** — Formulário de criação de brief: campos `theme` (texto livre), `mood` (dropdown: alegre/inspirador/educativo/emocional), `style` (cinematic / influencer_natural), `target_date`
- [ ] **AC4** — Submissão do formulário chama `POST /content/briefs` e adiciona peça ao calendário com `status = 'briefed'`
- [ ] **AC5** — Lista "Em produção" abaixo do calendário mostra todas as peças com status `image_generating`, `video_generating`, `assembly_pending`, etc. com indicador de progresso visual
- [ ] **AC6** — Limite visual: quando há 5 peças em produção, formulário de brief exibe aviso "Pipeline cheio — aguarde uma peça concluir antes de criar nova"
- [ ] **AC7** — Click em qualquer peça do calendário abre detail panel com: status atual, pipeline_log (timeline), assets (imagem/vídeo/áudio se disponíveis)
- [ ] **AC8** — Link direto para `/content/queue` quando há peças `pending_approval` — badge com contador

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

- [ ] `/content/` carrega e exibe calendário semanal com peças reais
- [ ] Formulário de brief cria peça e aparece na lista em produção
- [ ] Limite de 5 peças exibe aviso correto
- [ ] Click em peça abre detail com pipeline_log
- [ ] Badge de aprovação pendente aparece e linka para `/content/queue`

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `portal/src/app/(hq)/content/page.tsx` | Criar | Dashboard principal — calendário + brief form + produção |
| `portal/src/components/content/WeeklyCalendar.tsx` | Criar | Calendário semanal com status por dia |
| `portal/src/components/content/BriefForm.tsx` | Criar | Formulário de criação de brief |
| `portal/src/components/content/ProductionQueue.tsx` | Criar | Lista de peças em produção com status visual |
| `portal/src/components/content/PieceDetailPanel.tsx` | Criar | Panel de detalhe com pipeline_log timeline |
| `portal/src/app/api/content/briefs/route.ts` | Criar | Proxy POST /content/briefs e GET /content/briefs |
