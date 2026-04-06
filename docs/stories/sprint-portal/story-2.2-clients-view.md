# Story 2.2 — Clients View

**Sprint:** Portal Workstation v1 — Epic 2
**Status:** `po_accepted`
**Sequencia:** 2 de 2 — sem dependencia da 2.1. Depende de Epic 1 deployed.
**Design spec:** `docs/stories/sprint-portal/design-spec.md` — Secao 5
**UX spec:** `docs/stories/sprint-portal/ux-spec-epic1.md` — Secoes 2, 3, 4 (padroes de interacao, densidade, responsividade)

---

## User Story

> Como fundador da Sparkle,
> quero ver todos os meus clientes com saude, plano, MRR e ultima interacao em uma unica tela,
> para que eu identifique rapidamente clientes que precisam de atencao e tenha visao consolidada da receita.

---

## Contexto tecnico

**Arquivo principal:** `portal/app/(hq)/clients/page.tsx` (substituir placeholder do Epic 1)
**Arquivos secundarios:**
- `portal/components/hq/ClientCard.tsx` (novo)
- `portal/components/hq/ClientsGrid.tsx` (novo)
- `portal/components/hq/ClientsFilters.tsx` (novo)
- `portal/components/hq/MRRSummary.tsx` (novo)
- `portal/hooks/useHQData.ts` (existente — estender tipos `ClientRecord` e `ClientsData` se necessario)
- `portal/components/hq/DetailPanel.tsx` (existente — usar via `DetailPanelContext` para mostrar detalhes do cliente)
- `portal/components/hq/StatusBadge.tsx` (novo — reutilizavel para health indicators em qualquer view)
- `portal/components/hq/EmptyState.tsx` (existente — reutilizar)
- `portal/components/hq/LoadingSkeleton.tsx` (existente — estender com `ClientsSkeleton`)

**Pre-requisitos:**
- Epic 1 deployed (layout HQ, Sidebar, Header, DetailPanel, useHQData hooks)
- API proxy `GET /api/hq/clients` ja existe (Story 1.4)
- SWR hook `useClients()` ja existe em `hooks/useHQData.ts`
- Runtime API `GET /cockpit/clients` disponivel e retornando dados de clientes com health status
- Lucide React ja instalado

---

## Acceptance Criteria

- [x] **AC1** — Pagina `/hq/clients` renderiza com dados reais do `useClients()`. Substitui placeholder do Epic 1
- [x] **AC2** — Componente `<MRRSummary>` no topo da pagina exibe: MRR total formatado ("R$ 4.594"), contagem de clientes ativos, contagem por health (X green, Y yellow, Z red). Dados calculados a partir do array de clientes retornado pelo SWR
- [x] **AC3** — Componente `<ClientsGrid>` renderiza grid de cards responsivo. CSS Grid com `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))` e gap 12px
- [x] **AC4** — Componente `<ClientCard>` renderiza: nome do cliente, empresa/servico, plano ativo (badge), MRR formatado ("R$ 500/mes"), health status indicator (verde/amarelo/vermelho), ultima interacao como data relativa ("ha 2h", "ha 3 dias")
- [x] **AC5** — Componente `<StatusBadge>` reutilizavel com props `{ status: 'green' | 'yellow' | 'red', size?: 'sm' | 'md' }`. Renderiza circulo colorido + label opcional. Cores: green=#22c55e, yellow=#eab308, red=#ef4444. Circulo com tamanho 8px (sm) ou 12px (md)
- [x] **AC6** — Health status no card acompanhado de texto alem da cor (acessibilidade): green="Ativo", yellow="Atencao", red="Critico"
- [x] **AC7** — Click em `<ClientCard>` abre DetailPanel (via `useDetailPanel()`) com informacoes completas do cliente: nome, empresa, plano, MRR, health status com razao, ultima interacao (data absoluta + relativa), notas, status onboarding (se aplicavel), status Zenya (ativa/inativa)
- [x] **AC8** — Componente `<ClientsFilters>` com: campo de busca por nome (input text com icone Search), ordenacao (dropdown: health pior primeiro [default], MRR maior primeiro, nome A-Z). Filtros aplicados client-side sobre dados do SWR
- [x] **AC9** — Busca por nome filtra em tempo real conforme digitacao (debounce 300ms). Case-insensitive, busca parcial (substring match)
- [x] **AC10** — Ordenacao default: health (red primeiro, yellow, green). Dentro do mesmo health, por MRR decrescente
- [x] **AC11** — Titulo da pagina "Clientes" com icone Users (Lucide) + contagem total de clientes ativos
- [x] **AC12** — Loading state: `<ClientsSkeleton>` com shimmer em grid (6 cards placeholder) enquanto SWR carrega dados iniciais
- [x] **AC13** — Error state: se API falha, mostrar EmptyState com icone AlertCircle + texto "Nao foi possivel carregar clientes. Tentando novamente..."
- [x] **AC14** — Empty state (nenhum cliente): EmptyState com icone Users + texto "Nenhum cliente cadastrado"
- [x] **AC15** — Layout responsivo: em tela >= 1200px, grid com 3-4 cards por row. Em tela 960-1199px, 2 por row. Em tela < 960px, 1 por row. MRR Summary em row horizontal >= 960px, empilhado abaixo
- [x] **AC16** — Auto-refresh via SWR 30s. Mudancas refletidas sem flicker
- [x] **AC17** — Hover em ClientCard: sutil lift (translate-y -1px) + border glow (border-white/20 transition 150ms) + cursor pointer
- [x] **AC18** — Cards seguem density da workstation: padding 12px, text base 13px, gap 12px. Glass card style: `bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg`
- [x] **AC19** — Sidebar nav item "Clientes" fica com active state visual quando na pagina `/hq/clients` (handled by existing Sidebar pathname detection)

---

## Integration Verifications

- [ ] **IV1** — Pagina `/hq/clients` carrega e exibe dados reais do Runtime em < 3s (medir com DevTools Network)
- [ ] **IV2** — Navegacao via Sidebar: click em "Clientes" navega para `/hq/clients` com fade transition. Sidebar mostra active state no item Clientes
- [ ] **IV3** — Click em client card abre DetailPanel com dados corretos. Click em outro cliente substitui conteudo do panel (nao fecha e reabre). Escape fecha o panel
- [ ] **IV4** — Redimensionar de 1920px para 960px: grid ajusta colunas, MRR summary empilha, sidebar colapsa, sem overflow
- [ ] **IV5** — Digitar nome no campo busca: grid filtra em tempo real. Limpar busca: todos os clientes voltam
- [ ] **IV6** — Click no KPI "MRR" ou "Clientes" do Command Center navega corretamente para `/hq/clients`
- [ ] **IV7** — MRR total no MRRSummary confere com soma dos MRRs individuais dos cards visiveis

---

## Notas de implementacao

- **Reutilizar, nao recriar**: `useClients()`, `/api/hq/clients`, DetailPanel, EmptyState, LoadingSkeleton ja existem do Epic 1. Apenas estender se necessario
- **Tipos**: `ClientRecord` e `ClientsData` ja definidos em `hooks/useHQData.ts`. Se a API retorna campos adicionais (empresa, service_type, onboarding_status, zenya_active), estender a interface — nunca criar tipos duplicados
- **StatusBadge**: criar como componente reutilizavel em `portal/components/hq/StatusBadge.tsx`. Sera usado tambem na view Agentes (Epic 3) e em qualquer lugar que precise health indicator
- **MRR calculo**: somar `client.mrr` de todos os clientes ativos. Formatar com `toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })`. Se `mrr` for undefined/null, tratar como 0
- **Datas relativas**: usar mesmo utilitario que a Story 2.1 (se criado). `Intl.RelativeTimeFormat` ou calculo manual. Formato: "ha X dias", "ha X horas", "agora"
- **Busca com debounce**: usar `useState` para o input e `useMemo` com filtro. Debounce de 300ms pode ser implementado com `setTimeout` / `useRef` — evitar dependencia extra
- **Servico badge**: se a API retorna tipo de servico (Zenya, Trafego, Ambos), renderizar como badge pequeno no card com cores distintas
- **Health status calculation**: o Runtime ja calcula health (green/yellow/red) baseado em atividade recente. O frontend apenas exibe — nao recalcular
- **DetailPanel conteudo do cliente**: reutilizar o pattern de `DecisionsPending` que ja abre DetailPanel com dados de cliente (AC9 da Story 1.4). Estender com mais campos se necessario

---

## Handoff para @dev

```
---
GATE_CONCLUIDO: Gate 3 — Stories prontas
STATUS: AGUARDANDO_DEV
PROXIMO: @dev
SPRINT_ITEM: PORTAL-WS-2.2

ENTREGA:
  - Story: docs/stories/sprint-portal/story-2.2-clients-view.md
  - Design spec (secao 5): docs/stories/sprint-portal/design-spec.md
  - UX spec (secoes 2, 3, 4): docs/stories/sprint-portal/ux-spec-epic1.md
  - PRD (FR3): docs/prd/portal-workstation-prd.md

DEPENDENCIA: Epic 1 deployed (layout, auth, DetailPanel, useHQData, proxies)

SUPABASE_ATUALIZADO: nao aplicavel (consome APIs do Runtime via proxy existente)

PROMPT_PARA_PROXIMO: |
  Voce e @dev (Dex). Contexto direto — comece aqui.

  O QUE FAZER:
  Implementar a View Clientes — grid de cards com health status, MRR,
  plano, ultima interacao. MRR summary no topo. Busca por nome.
  Ordenacao por health/MRR/nome. Click em cliente abre DetailPanel.

  ARQUIVOS A CRIAR:
  1. portal/components/hq/ClientCard.tsx — card de cliente individual
  2. portal/components/hq/ClientsGrid.tsx — container grid de cards
  3. portal/components/hq/ClientsFilters.tsx — busca + ordenacao
  4. portal/components/hq/MRRSummary.tsx — resumo MRR + contagens no topo
  5. portal/components/hq/StatusBadge.tsx — badge reutilizavel de health status

  ARQUIVOS A MODIFICAR:
  1. portal/app/(hq)/clients/page.tsx — substituir placeholder por Clients view real
  2. portal/hooks/useHQData.ts — estender tipos ClientRecord/ClientsData se necessario
  3. portal/components/hq/LoadingSkeleton.tsx — adicionar ClientsSkeleton

  JA EXISTE (NAO RECRIAR):
  - API proxy: portal/app/api/hq/clients/route.ts
  - SWR hook: useClients() em portal/hooks/useHQData.ts
  - DetailPanel: portal/components/hq/DetailPanel.tsx + DetailPanelContext.tsx
  - EmptyState: portal/components/hq/EmptyState.tsx
  - LoadingSkeleton: portal/components/hq/LoadingSkeleton.tsx (estender)

  RUNTIME API CONSUMIDA (ja existe):
  - GET /cockpit/clients → lista clientes com health_status, MRR, plano

  CRITERIOS DE SAIDA:
  - [ ] AC1 a AC19 todos implementados
  - [ ] IV1 a IV7 todos passando
  - [ ] MRR total correto e coerente com cards individuais
  - [ ] Busca por nome funcional com debounce
  - [ ] DetailPanel abre com dados completos do cliente
---
```

---

## PO Validation
**Revisor:** @po (Pax) | **Data:** 2026-04-06 | **Decisao:** `PASS`
- PRD alignment: FR3 fully covered (grid, health indicator, service badge, detail panel, ordering, MRR total)
- ACs: 19/19 specific and testable (exact CSS values, color codes, timing, format strings)
- IVs: 7/7 integration verifications with clear pass/fail criteria
- Design spec: correctly references design-spec.md section 5 + ux-spec-epic1.md sections 2,3,4
- Dependencies: clear — Epic 1 (layout, sidebar, header, DetailPanel, useHQData, API proxy) all listed
- Pre-requisites: useClients() hook, /api/hq/clients proxy, Lucide React all confirmed existing
**STATUS: `APROVADA` -> proximo: @dev**

---

## QA Results

**Revisor:** @qa (Quinn) | **Data:** 2026-04-06 | **Decisao:** `PASS`

### AC Verification (19/19 PASS)

| AC | Verdict | Evidence |
|----|---------|----------|
| AC1 | PASS | `page.tsx` calls `useClients()`, renders real data |
| AC2 | PASS | `MRRSummary.tsx` — MRR total (currency format pt-BR), active count, green/yellow/red counts with colored dots |
| AC3 | PASS | `ClientsGrid.tsx` — `gridTemplateColumns: repeat(auto-fill, minmax(280px, 1fr))`, `gap-3` (12px) |
| AC4 | PASS | `ClientCard.tsx` — name, empresa, plan badge, MRR "R$ X/mes", health status, relative time |
| AC5 | PASS | `StatusBadge.tsx` — props match spec, dot 8px (sm) / 12px (md), colors #22c55e/#eab308/#ef4444 |
| AC6 | PASS | `StatusBadge.tsx` — green="Ativo", yellow="Atencao", red="Critico" + sr-only for screen readers |
| AC7 | PASS | `ClientsGrid.tsx` `ClientDetailContent` — all fields: name, empresa, plan, MRR, health+reason, last interaction (absolute+relative), service, onboarding, zenya status, notes |
| AC8 | PASS | `ClientsFilters.tsx` — Search icon input + select dropdown (health/mrr/name) |
| AC9 | PASS | 300ms debounce via setTimeout/useRef, case-insensitive `toLowerCase().includes()` |
| AC10 | PASS | Default `useState('health')`, sort weights red=0 yellow=1 green=2, MRR desc tiebreaker |
| AC11 | PASS | "Clientes" h1 + Users icon + active count span |
| AC12 | PASS | `ClientsSkeleton count={6}` with matching grid layout and shimmer animation |
| AC13 | PASS | `EmptyState` + `AlertCircle` + "Nao foi possivel carregar clientes" / "Tentando novamente..." |
| AC14 | PASS | `EmptyState` + `Users` + "Nenhum cliente cadastrado" |
| AC15 | PASS | `auto-fill minmax(280px, 1fr)` gives 3-4/2/1 cols at 1200+/960-1199/<960. MRRSummary `grid-cols-1 sm:grid-cols-3` |
| AC16 | PASS | SWR `refreshInterval: 30000` in `useHQData.ts` |
| AC17 | PASS | `hover:-translate-y-[1px] hover:border-white/20 transition-all duration-150 cursor-pointer` |
| AC18 | PASS | `p-3`=12px, text `0.8125rem`=13px, `gap-3`=12px, glass: `bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg` |
| AC19 | PASS | Sidebar pathname detection (existing infra from Epic 1) |

### Observations (non-blocking)

1. **Code duplication**: `relativeTime()` and `formatMRR()` duplicated in `ClientCard.tsx` and `ClientsGrid.tsx`. Recommend extracting to shared util in a future cleanup pass.
2. **Search scope**: Search also matches `empresa` field beyond AC9 spec (nome only). Additive behavior, not a defect.
3. **Accessibility**: Good use of `role="button"`, `tabIndex`, `aria-label`, `aria-hidden`, and `sr-only` across components.

### IVs (pending manual browser verification)

IVs 1-7 require live browser testing against the deployed portal with real Runtime data. Code-level review confirms all integration points are correctly wired. Recommend @dev or @devops run IV verification after deploy.

**STATUS: `qa_approved` -> proximo: IV verification em browser**

---

## PO Acceptance
**Revisor:** @po (Pax) | **Data:** 2026-04-06 | **Decisao:** `ACEITA`
- QA gate: PASS (Quinn) — 19/19 ACs, IVs pending browser (code-level confirmed)
- ACs cobertos: 19/19
- PRD alignment: FR3 covered — grid clients, health indicator, service badge, MRR total, detail panel, ordering, busca por nome
- Observacoes QA aceitas: relativeTime/formatMRR duplicados (cleanup futuro), busca inclui empresa alem de nome (aditivo, nao defeito), acessibilidade bem implementada
- IVs 1-7: code-level wiring confirmed, browser verification pendente pos-deploy (nao bloqueia acceptance)
**STATUS: `po_accepted`**
*-- Pax, equilibrando prioridades*

---

*Story 2.2 — Portal Workstation v1 | River, mantendo o fluxo*
