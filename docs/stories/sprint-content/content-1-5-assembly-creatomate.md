---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.5
title: "Assembly (Creatomate) — Montagem do Reel Final"
status: Deferred
priority: P2
executor: "@dev"
sprint: Content Wave 2
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.2, CONTENT-1.3, CONTENT-1.4]
unblocks: [CONTENT-1.6]
estimated_effort: 4-5h de agente (@dev)
blocker: "CREATOMATE_API_KEY — Mauro obtém em creatomate.com → API | CREATOMATE_TEMPLATE_ID — Mauro cria template no dashboard Creatomate com variáveis: video_url, audio_url, caption_text, logo_url"
---

# Story 1.5 — Assembly (Creatomate) — Montagem do Reel Final

> ⚠️ **DEFERRED — Arquitetura v1.1 (2026-04-07)**
> Voz manual por Mauro via ElevenLabs voice changer. Assembly automático removido do MVP.
> Retorna em Content Wave 2 quando pipeline for totalmente autônomo.

**Sprint:** Content Wave 2
**Status:** `Deferred`
**Sequência:** 6 de 13
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR5
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como pipeline de conteúdo,
> quero combinar o vídeo gerado, o áudio da Zenya, a legenda animada e o branding Sparkle/Zenya em um único .mp4 9:16 pronto para publicação,
> para que Mauro receba uma peça completa e profissional na fila de aprovação sem precisar editar nada.

---

## Contexto Técnico

**Estado atual:** Nenhuma integração com Creatomate existe no Runtime.

**Estado alvo:** `assembler.py` implementa `AssemblerProtocol`; `CreatomateAssembler` monta o .mp4 final via API Creatomate com template parametrizável; arquivo salvo no Supabase Storage; status avança `assembly_pending` → `assembly_done`.

**Arquitetura de abstração:** `assembler.py` usa `AssemblerProtocol` para permitir swap futuro para Remotion sem mudar o pipeline.

**⚠️ BLOCKER:** `CREATOMATE_API_KEY` precisa estar em variável de ambiente antes dos testes.

---

## Acceptance Criteria

- [ ] **AC1** — `AssemblerProtocol` definido com interface: `async def assemble(video_url, audio_url, caption, piece_id) -> str`
- [ ] **AC2** — `CreatomateAssembler` implementa o protocolo: chama Creatomate API com template parametrizável
- [ ] **AC3** — Template Creatomate aceita parâmetros: `{{video_url}}`, `{{audio_url}}`, `{{caption_text}}`, `{{logo_url}}`
- [ ] **AC4** — Output .mp4 em formato 9:16, resolução mínima 1080×1920
- [ ] **AC5** — Legenda animada sincronizada com narração (se `audio_url` presente); sem narração, sem legenda animada
- [ ] **AC6** — .mp4 final salvo no Supabase Storage em `content-assets/final/{content_piece_id}.mp4`
- [ ] **AC7** — `content_pieces.final_url` atualizado; `status` avança para `assembly_done`
- [ ] **AC8** — Falha no Creatomate atualiza `status = 'assembly_failed'` e registra em `error_log` — não bloqueia pipeline

---

## Dev Notes

### AssemblerProtocol
```python
from typing import Protocol

class AssemblerProtocol(Protocol):
    async def assemble(
        self,
        video_url: str,
        audio_url: str | None,
        caption: str,
        piece_id: str
    ) -> str:
        """Returns: Storage path do .mp4 final"""
        ...
```

### Creatomate API — renderização
```python
async def assemble(self, video_url, audio_url, caption, piece_id) -> str:
    payload = {
        "template_id": CREATOMATE_TEMPLATE_ID,  # configurado no Creatomate dashboard
        "modifications": {
            "video_url": video_url,
            "audio_url": audio_url or "",
            "caption_text": caption[:150],  # primeiras 150 chars para legenda animada
            "logo_url": SPARKLE_LOGO_URL,
        },
        "output_format": "mp4",
        "width": 1080,
        "height": 1920,
    }
    resp = await httpx.post(
        "https://api.creatomate.com/v1/renders",
        headers={"Authorization": f"Bearer {self.api_key}"},
        json=payload
    )
    render_id = resp.json()[0]["id"]
    
    # Polling
    for _ in range(60):
        await asyncio.sleep(5)
        status_resp = await httpx.get(
            f"https://api.creatomate.com/v1/renders/{render_id}",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        render = status_resp.json()
        if render["status"] == "succeeded":
            # Download e upload para Supabase Storage
            mp4_bytes = await httpx.get(render["url"]).content
            path = f"content-assets/final/{piece_id}.mp4"
            supabase.storage.from_("content").upload(path, mp4_bytes)
            return path
        if render["status"] == "failed":
            raise RuntimeError(f"Creatomate render failed: {render.get('error_message')}")
    
    raise TimeoutError("Creatomate timeout após 5 minutos")
```

### Template Creatomate
- Criar template no dashboard Creatomate com as variáveis acima
- Salvar `CREATOMATE_TEMPLATE_ID` como variável de ambiente
- Template deve ter: camada de vídeo (background), camada de áudio, camada de legenda (lower thirds animado), camada de logo (canto inferior)

---

## Integration Verifications

- [ ] `CREATOMATE_API_KEY` e `CREATOMATE_TEMPLATE_ID` disponíveis no Runtime
- [ ] Template criado no Creatomate dashboard com as 4 variáveis
- [ ] Render com `video_url` + `audio_url` + `caption` retorna `render_id`
- [ ] Polling detecta `status == "succeeded"` e URL do .mp4 é válida
- [ ] .mp4 salvo no Supabase Storage (`content-assets/final/`)
- [ ] `content_pieces.final_url` preenchido e `status = "assembly_done"`
- [ ] Render com `audio_url = ""` (sem narração) funciona sem legenda animada
- [ ] Falha simulada resulta em `status = "assembly_failed"` sem crash

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/assembler.py` | Criar | AssemblerProtocol + CreatomateAssembler |
| `tests/test_assembler.py` | Criar | Testes: render, polling, storage, failure handling |
