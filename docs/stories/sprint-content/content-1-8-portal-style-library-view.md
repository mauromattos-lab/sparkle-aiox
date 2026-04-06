---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.8
title: "Portal — Style Library View (Curadoria Interface)"
status: TODO
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

- [ ] **AC1** — `/content/library` exibe grid de imagens da `style_library` com filtros: Tier A / Tier B / Tier C / Todas
- [ ] **AC2** — Cada card de imagem exibe: thumbnail, tier badge (A/B/C), `use_count`, `style_type`, botões de reação (❤️/✗/→)
- [ ] **AC3** — Reação em imagem já classificada atualiza `mauro_score` e pode reclassificar tier (via `POST /content/library/{id}/react`)
- [ ] **AC4** — Stats no topo da página: total Tier A, Tier B, Tier C; total de gerações usando a biblioteca
- [ ] **AC5** — Busca por `style_type` (cinematic / influencer_natural) dentro do grid
- [ ] **AC6** — Imagens Tier A têm indicação visual destacada (borda dourada ou badge especial)
- [ ] **AC7** — Botão "Ver similares" em qualquer imagem abre sidebar com as 10 mais similares por CLIP (`GET /content/library/similar/{id}`)
- [ ] **AC8** — Upload de novas imagens via drag-and-drop ou botão, com progresso de upload e cálculo de embedding

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

- [ ] `/content/library` carrega imagens da style_library via API
- [ ] Filtros por tier funcionam corretamente
- [ ] Reação atualiza score e badge visual em tempo real (sem reload)
- [ ] "Ver similares" abre sidebar com imagens similares ordenadas por CLIP
- [ ] Upload de nova imagem aparece na grid após processamento
- [ ] Stats no topo refletem contagens reais do banco

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `portal/src/app/(hq)/content/library/page.tsx` | Criar | Style Library View — grid + filtros + stats |
| `portal/src/components/content/StyleLibraryCard.tsx` | Criar | Card individual com tier badge + reações |
| `portal/src/components/content/SimilarSidebar.tsx` | Criar | Sidebar de imagens similares por CLIP |
| `portal/src/app/api/content/library/route.ts` | Criar | Proxy GET /content/library |
| `portal/src/app/api/content/library/[id]/react/route.ts` | Criar | Proxy POST react |
| `portal/src/app/api/content/library/similar/[id]/route.ts` | Criar | Proxy GET similar |
