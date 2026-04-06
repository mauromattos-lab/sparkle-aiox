---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.7
title: "Portal — Content Queue View (Aprovação)"
status: TODO
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

- [ ] **AC1** — `/content/queue` exibe fila de peças com `status = 'pending_approval'` carregada via `GET /content/queue`
- [ ] **AC2** — Preview fullscreen: para imagens, exibe `<img>` ocupando a tela; para vídeos com `final_url`, exibe `<video>` com autoplay muted + botão unmute
- [ ] **AC3** — Navegação entre peças: botões Anterior / Próximo com contador "3 de 5 hoje"
- [ ] **AC4** — Caption exibida abaixo do preview com botão de edição inline (click para editar, Enter para salvar, chamada a `PATCH /content/pieces/{id}/caption`)
- [ ] **AC5** — Ação ✅ Aprovar: chama `POST /content/pieces/{id}/approve`, avança para próxima peça, atualiza contador
- [ ] **AC6** — Ação ❌ Rejeitar: abre modal com campo de texto para motivo (obrigatório), chama `POST /content/pieces/{id}/reject` com `{reason: "..."}`, avança para próxima
- [ ] **AC7** — Ação ✏️ Editar: já coberta pelo AC4 (edição inline de caption)
- [ ] **AC8** — Botão "Aprovar todos restantes" na barra superior: chama approve para todas as peças pending em sequência com loading state
- [ ] **AC9** — Fila vazia exibe estado empty: "Nenhum conteúdo aguardando aprovação" com link para `/content/`
- [ ] **AC10** — Loading state durante chamadas de API (skeleton ou spinner); erro de API exibe toast com mensagem

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

- [ ] `/content/queue` carrega peças `pending_approval` corretamente
- [ ] Preview de vídeo exibe com autoplay (muted por padrão)
- [ ] Edição de caption salva via PATCH e reflete na UI sem reload
- [ ] Aprovar peça chama API e avança para próxima
- [ ] Rejeitar sem motivo não submete (botão desabilitado até texto digitado)
- [ ] "Aprovar todos" aprova sequencialmente e exibe loading correto
- [ ] Fila vazia exibe estado empty adequado
- [ ] Responsivo em mobile (Mauro pode usar no celular)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `portal/src/app/(hq)/content/queue/page.tsx` | Criar | Content Queue View — aprovação fullscreen |
| `portal/src/components/content/VideoPreview.tsx` | Criar | Video player com autoplay/mute toggle |
| `portal/src/components/content/CaptionEditor.tsx` | Criar | Caption editável inline |
| `portal/src/components/content/ActionBar.tsx` | Criar | Botões Aprovar/Rejeitar/Nav |
| `portal/src/components/content/RejectModal.tsx` | Criar | Modal de rejeição com campo obrigatório |
| `portal/src/app/api/content/queue/route.ts` | Criar | Proxy Next.js → Runtime GET /content/queue |
| `portal/src/app/api/content/pieces/[id]/approve/route.ts` | Criar | Proxy POST approve |
| `portal/src/app/api/content/pieces/[id]/reject/route.ts` | Criar | Proxy POST reject |
| `portal/src/app/api/content/pieces/[id]/caption/route.ts` | Criar | Proxy PATCH caption |
