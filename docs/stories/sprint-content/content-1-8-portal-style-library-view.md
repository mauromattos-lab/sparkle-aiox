---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.8
title: "Portal — Style Library View (Curadoria Interface)"
status: Done
priority: P0
executor: "@dev (Portal Next.js)"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-0.1, CONTENT-1.6]
unblocks: []
estimated_effort: 4-5h de agente (@dev)
---

# Story 1.8 — Portal — Style Library View (Curadoria Interface)

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 9 de 13 (paralelo com 1.7 e 1.9)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR1
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como Mauro,
> quero navegar pela Style Library do Portal e ver quais imagens da Zenya estão classificadas como Tier A, B e C, além de poder reagir a novas imagens para refinar a curadoria ao longo do tempo,
> para que eu mantenha controle sobre quais referências visuais o pipeline usa para gerar novo conteúdo.

---

## Contexto Técnico

**Nota:** A interface de curadoria inicial (upload + reação + CLIP) foi implementada em CONTENT-0.1. Esta story cria a **view permanente** no Portal para gerenciamento contínuo da Style Library após a curadoria inicial estar completa.

**Estado alvo:** `/content/library` exibe grid de imagens filtradas por tier, com status de uso, opção de reclassificar e visualizar stats da biblioteca.

---

## Acceptance Criteria

- [x] **AC1** — `/content/library` exibe grid de imagens da `style_library` com filtros: Tier A / Tier B / Tier C / Todas
- [x] **AC2** — Cada card de imagem exibe: thumbnail, tier badge (A/B/C), `use_count`, `style_type`, botões de reação (❤️/✗/→)
- [x] **AC3** — Reação em imagem já classificada atualiza `mauro_score` e pode reclassificar tier (via `POST /content/library/{id}/react`)
- [x] **AC4** — Stats no topo da página: total Tier A, Tier B, Tier C; total de gerações usando a biblioteca
- [x] **AC5** — Busca por `style_type` (cinematic / influencer_natural) dentro do grid
- [x] **AC6** — Imagens Tier A têm indicação visual destacada (borda dourada ou badge especial)
- [x] **AC7** — Botão "Ver similares" em qualquer imagem abre sidebar com as 10 mais similares por CLIP (`GET /content/library/similar/{id}`)
- [x] **AC8** — Upload de novas imagens via drag-and-drop ou botão, com progresso de upload e cálculo de embedding

---

## Dev Notes

### Grid com filtros
```tsx
// Filtros de tier
const [tierFilter, setTierFilter] = useState<'all' | 'A' | 'B' | 'C'>('all')

const filtered = images.filter(img =>
  tierFilter === 'all' ? true : img.tier === tierFilter
)
```

### Card de imagem
```tsx
function StyleLibraryCard({ item }: { item: StyleLibraryItem }) {
  return (
    <div className={cn(
      "relative rounded-lg overflow-hidden border-2",
      item.tier === 'A' && "border-yellow-400",
      item.tier === 'B' && "border-gray-400",
      item.tier === 'C' && "border-gray-200"
    )}>
      <img src={item.storage_path} className="w-full aspect-[9/16] object-cover" />
      <div className="absolute top-2 left-2">
        <Badge tier={item.tier} />
      </div>
      <div className="p-2 flex justify-between items-center bg-black/80">
        <span className="text-xs text-gray-400">{item.use_count}x usado</span>
        <ReactionButtons itemId={item.id} currentScore={item.mauro_score} />
      </div>
    </div>
  )
}
```

---

## Integration Verifications

- [x] `/content/library` carrega imagens da style_library via API
- [x] Filtros por tier funcionam corretamente
- [x] Reação atualiza score e badge visual em tempo real (sem reload)
- [x] "Ver similares" abre sidebar com imagens similares ordenadas por CLIP
- [x] Upload de nova imagem aparece na grid após processamento
- [x] Stats no topo refletem contagens reais do banco

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `portal/app/hq/content/library/page.tsx` | Atualizado | Adicionados AC5 (busca style_type) + AC7 (SimilarSidebar inline) ao page CONTENT-0.1 existente |
| `portal/app/api/hq/content/library/similar/[id]/route.ts` | Criado | Proxy GET /content/library/similar/{id} |

---

## Dev Agent Record

**Agent Model:** claude-sonnet-4-6
**Completed:** 2026-04-07
**Completion Notes:** ACs 1-6, 8 já cobertos pelo CONTENT-0.1 existente (`portal/app/hq/content/library/page.tsx`). AC5 adicionado: campo de busca por style_type inline com filtro reativo. AC7 adicionado: SimilarSidebar component que aparece no hover de cada card e busca via GET /content/library/similar/{id}. Proxy de API criado. Build passou sem erros.
**Change Log:**
- Atualizado `portal/app/hq/content/library/page.tsx` — search bar + SimilarSidebar + onViewSimilar prop
- Criado `portal/app/api/hq/content/library/similar/[id]/route.ts`

---

## QA Results

**Revisor:** @qa (Quinn) — 2026-04-07
**Resultado:** PASS com CONCERNS ⚠️

| AC | Status | Nota |
|----|--------|------|
| AC1 | ✅ | Grid com filtros tier — coberto por CONTENT-0.1 existente |
| AC2 | ✅ | Cards com thumbnail, tier badge, use_count, style_type, botões de reação |
| AC3 | ✅ | Reação via POST /content/library/{id}/react — coberto por 0.1 |
| AC4 | ✅ | Stats no topo — coberto por 0.1 |
| AC5 | ✅ | Busca por style_type via filtro reativo inline |
| AC6 | ✅ | Tier A com borda dourada — coberto por 0.1 |
| AC7 | ✅ | Endpoint GET /content/library/similar/{id} implementado em style_library.py:201 + montado via include_router — concern anterior era falso positivo |
| AC8 | ✅ | Upload via drag-and-drop — coberto por 0.1 |

**Concerns:**
- Nenhum concern bloqueante. Concern AC7 do review anterior foi falso positivo: @dev confirmou que o endpoint existe em `sparkle-runtime/runtime/content/style_library.py` (linha 201, `@router.get("/similar/{item_id}")`), incluído em `router.py` via `include_router` e montado em `/content` pelo `main.py`. Path final `/content/library/similar/{id}` está correto.

**Decisão final: PASS** ✅
