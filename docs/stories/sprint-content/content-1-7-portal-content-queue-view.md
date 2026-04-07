---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.7
title: "Portal — Content Queue View (Aprovação)"
status: Ready for Review
priority: P0
executor: "@dev (Portal Next.js)"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.6]
unblocks: [CONTENT-1.12]
estimated_effort: 5-6h de agente (@dev)
---

# Story 1.7 — Portal — Content Queue View (Aprovação)

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 8 de 13 (paralelo com 1.8 e 1.9)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR7
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como Mauro,
> quero uma tela de aprovação no Portal com preview fullscreen do vídeo, caption editável e botões de ação (Aprovar/Editar/Rejeitar),
> para que eu revise e aprove conteúdo da Zenya rapidamente sem precisar usar o WhatsApp ou ferramentas externas.

---

## Contexto Técnico

**Estado atual:** Portal existe em Next.js mas não tem nenhuma view de conteúdo.

**Estado alvo:** `/content/queue` no Portal exibe fila de `pending_approval` com preview fullscreen, navegação entre peças, caption editável inline, aprovação em lote.

**Referência arquitetural:**
```
portal/src/app/(hq)/content/queue/page.tsx
```

---

## Acceptance Criteria

- [x] **AC1** — `/content/queue` exibe fila de peças com `status = 'pending_approval'` carregada via `GET /content/queue`
- [x] **AC2** — Preview fullscreen: para imagens, exibe `<img>` ocupando a tela; para vídeos com `final_url`, exibe `<video>` com autoplay muted + botão unmute
- [x] **AC3** — Navegação entre peças: botões Anterior / Próximo com contador "3 de 5 hoje"
- [x] **AC4** — Caption exibida abaixo do preview com botão de edição inline (click para editar, Enter para salvar, chamada a `PATCH /content/pieces/{id}/caption`)
- [x] **AC5** — Ação ✅ Aprovar: chama `POST /content/pieces/{id}/approve`, avança para próxima peça, atualiza contador
- [x] **AC6** — Ação ❌ Rejeitar: abre modal com campo de texto para motivo (obrigatório), chama `POST /content/pieces/{id}/reject` com `{reason: "..."}`, avança para próxima
- [x] **AC7** — Ação ✏️ Editar: já coberta pelo AC4 (edição inline de caption)
- [x] **AC8** — Botão "Aprovar todos restantes" na barra superior: chama approve para todas as peças pending em sequência com loading state
- [x] **AC9** — Fila vazia exibe estado empty: "Nenhum conteúdo aguardando aprovação" com link para `/content/`
- [x] **AC10** — Loading state durante chamadas de API (skeleton ou spinner); erro de API exibe toast com mensagem

---

## Dev Notes

### Estrutura da página
```tsx
// /content/queue/page.tsx
'use client'

export default function ContentQueuePage() {
  const [pieces, setPieces] = useState<ContentPiece[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false)

  const current = pieces[currentIndex]

  return (
    <div className="h-screen flex flex-col bg-black">
      {/* Header: contador + "Aprovar todos" */}
      <QueueHeader total={pieces.length} current={currentIndex + 1} onApproveAll={handleApproveAll} />
      
      {/* Preview fullscreen */}
      <div className="flex-1 relative">
        {current?.final_url ? (
          <VideoPreview url={current.final_url} />
        ) : (
          <ImagePreview url={current?.image_url} />
        )}
      </div>
      
      {/* Caption editável */}
      <CaptionEditor
        value={current?.caption}
        onSave={(caption) => updateCaption(current.id, caption)}
      />
      
      {/* Ações */}
      <ActionBar
        onApprove={() => approve(current.id)}
        onReject={() => setIsRejectModalOpen(true)}
        onPrev={() => setCurrentIndex(i => i - 1)}
        onNext={() => setCurrentIndex(i => i + 1)}
        canPrev={currentIndex > 0}
        canNext={currentIndex < pieces.length - 1}
      />
      
      {/* Modal de rejeição */}
      <RejectModal
        open={isRejectModalOpen}
        onSubmit={(reason) => reject(current.id, reason)}
        onClose={() => setIsRejectModalOpen(false)}
      />
    </div>
  )
}
```

### Chamadas de API (via proxy Next.js → Runtime)
```
GET  /api/content/queue                      → lista pending_approval
POST /api/content/pieces/{id}/approve        → aprovar
POST /api/content/pieces/{id}/reject         → rejeitar (body: {reason})
PATCH /api/content/pieces/{id}/caption       → editar caption (body: {caption})
```

### VideoPreview — autoplay + unmute
```tsx
function VideoPreview({ url }: { url: string }) {
  const [muted, setMuted] = useState(true)
  return (
    <div className="relative w-full h-full">
      <video
        src={url}
        autoPlay
        loop
        muted={muted}
        className="w-full h-full object-contain"
      />
      <button
        onClick={() => setMuted(m => !m)}
        className="absolute bottom-4 right-4 bg-black/50 rounded-full p-2"
      >
        {muted ? <VolumeOff /> : <Volume2 />}
      </button>
    </div>
  )
}
```

---

## Integration Verifications

- [x] `/content/queue` carrega peças `pending_approval` corretamente
- [x] Preview de vídeo exibe com autoplay (muted por padrão)
- [x] Edição de caption salva via PATCH e reflete na UI sem reload
- [x] Aprovar peça chama API e avança para próxima
- [x] Rejeitar sem motivo não submete (botão desabilitado até texto digitado)
- [x] "Aprovar todos" aprova sequencialmente e exibe loading correto
- [x] Fila vazia exibe estado empty adequado
- [x] Responsivo em mobile (Mauro pode usar no celular)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `portal/app/hq/content/queue/page.tsx` | Criado | Content Queue View — fullscreen com VideoPreview, CaptionEditor, RejectModal, ActionBar inline |
| `portal/app/api/hq/content/queue/route.ts` | Criado | Proxy GET /content/queue |
| `portal/app/api/hq/content/pieces/[id]/approve/route.ts` | Criado | Proxy POST approve |
| `portal/app/api/hq/content/pieces/[id]/reject/route.ts` | Criado | Proxy POST reject |
| `portal/app/api/hq/content/pieces/[id]/caption/route.ts` | Criado | Proxy PATCH caption |
| `portal/app/api/hq/content/pieces/route.ts` | Criado | Proxy GET /content/pieces (para calendar) |

---

## Dev Agent Record

**Agent Model:** claude-sonnet-4-6
**Completed:** 2026-04-07
**Completion Notes:** Todos os 10 ACs implementados. Componentes inline no page.tsx (VideoPreview, CaptionEditor, RejectModal, ActionBar). Build Next.js passou sem erros. Nota: portal usa `app/hq/` (não `app/(hq)/` como indicado no story) — padrão real do projeto respeitado. `video_url` usado para preview conforme instrução arquitetural (Creatomate removido).
**Change Log:**
- Criado `portal/app/hq/content/queue/page.tsx`
- Criados 4 proxies de API em `portal/app/api/hq/content/pieces/[id]/`
- Criado `portal/app/api/hq/content/queue/route.ts`
- Criado `portal/app/api/hq/content/pieces/route.ts`

---

## QA Results

**Revisor:** @qa (Quinn) — 2026-04-07
**Resultado:** PASS ✅

| AC | Status | Nota |
|----|--------|------|
| AC1 | ✅ | fetch /api/hq/content/queue, normaliza {pieces:[]} e array direto |
| AC2 | ✅ | VideoPreview autoplay+muted+loop, ImagePreview, usa video_url correto |
| AC3 | ✅ | Counter "N de M hoje", prev/next com disabled guard |
| AC4 | ✅ | CaptionEditor inline, Enter salva, Escape cancela, PATCH /caption |
| AC5 | ✅ | handleApprove remove peça, avança index com Math.min |
| AC6 | ✅ | RejectModal disabled sem reason.trim() |
| AC7 | ✅ | Coberto por AC4 |
| AC8 | ✅ | handleApproveAll sequencial com loading dedicado |
| AC9 | ✅ | Empty state + link para /hq/content |
| AC10 | ✅ | Spinner em loading, toast em erro/sucesso |

**Concerns (não bloqueantes):**
- BAIXO: handleApproveAll não para em erro individual — silent failures possíveis
- BAIXO: setPieces([]) otimista após approve all (sem reload de confirmação)
