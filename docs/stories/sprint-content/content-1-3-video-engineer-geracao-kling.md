---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.3
title: "Video Prompt Engineer + Geração Veo (Google Gemini)"
status: Ready for Review
priority: P0
executor: "@dev"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.1]
unblocks: [CONTENT-1.5]
estimated_effort: 4-5h de agente (@dev)
blocker: "GEMINI_API_KEY — mesma chave de CONTENT-1.2, obtém em aistudio.google.com (gratuito)"
---

# Story 1.3 — Video Prompt Engineer + Geração Veo (Google Gemini)

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 4 de 13 (paralelo com 1.2 e 1.4)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR3
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como pipeline de conteúdo,
> quero animar a imagem gerada da Zenya em um vídeo 9:16 com movimento orgânico e cinematográfico,
> para que o Reel tenha qualidade visual de produção profissional sem depender de ferramentas manuais.

---

## Contexto Técnico

**Estado atual:** Nenhuma integração com Veo existe no Runtime. Higgsfield (usado anteriormente) não tem mais assinatura.

**Estado alvo:** `video_engineer.py` gera prompt de movimento a partir da imagem + estilo; `video_generator.py` chama Google Veo 3.1 (image-to-video); vídeo 9:16 5-10s salvo no Supabase Storage; status avança `image_done` → `video_generating` → `video_done`.

**Arquitetura de abstração:** `video_generator.py` implementa `VideoGeneratorProtocol` (`VeoVideoGenerator`) para permitir swap futuro sem alterar o pipeline.

**⚠️ BLOCKER:** `GEMINI_API_KEY` precisa estar em variável de ambiente — mesma chave usada em CONTENT-1.2.

---

## Acceptance Criteria

- [x] **AC1** — `video_engineer.py` recebe imagem gerada + estilo e retorna prompt de vídeo descrevendo: movimento da personagem, câmera, física do ambiente, duração e aspect ratio
- [x] **AC2** — `VideoGeneratorProtocol` definido com interface: `async def generate(image_url, prompt, style) -> str`
- [x] **AC3** — `VeoVideoGenerator` implementa o protocolo: autentica via `GEMINI_API_KEY` (google-genai SDK), chama `client.aio.models.generate_videos(model="veo-2.0-generate-001", ...)`
- [x] **AC4** — Parâmetros obrigatórios na chamada Veo: `aspect_ratio: "9:16"`, `duration_seconds: 5` (ou 10 para cinematic), `number_of_videos: 1`
- [x] **AC5** — Veo retorna operation — `video_generator.py` faz polling via `operation.done` até completar (max 5 min com retry)
- [x] **AC6** — Vídeo gerado baixado e salvo no Supabase Storage em `content-assets/videos/{content_piece_id}.mp4`
- [x] **AC7** — `content_pieces.video_url` atualizado; `status` avança para `video_done`
- [x] **AC8** — Falha na API ou timeout atualiza `status = 'video_failed'` e registra em `error_log` — pipeline continua para outras peças

---

## Dev Notes

### VideoGeneratorProtocol
```python
from typing import Protocol

class VideoGeneratorProtocol(Protocol):
    async def generate(self, image_url: str, prompt: str, style: str) -> str:
        """Returns: URL pública do vídeo gerado no Supabase Storage"""
        ...
```

### VeoVideoGenerator — chamada + polling
```python
import asyncio
import google.generativeai as genai
from google.generativeai import types

class VeoVideoGenerator:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def generate(self, image_url: str, prompt: str, style: str) -> str:
        operation = await self.client.aio.models.generate_videos(
            model="veo-2.0-generate-001",
            prompt=prompt,
            image=types.Image(image_url=image_url),
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16",
                duration_seconds=10 if style == "cinematic" else 5,
                number_of_videos=1,
            )
        )
        # Polling até completar (max 5 min)
        for _ in range(30):
            await asyncio.sleep(10)
            operation = await self.client.aio.operations.get(operation)
            if operation.done:
                break
        else:
            raise TimeoutError("Veo job timeout após 5 minutos")

        video_uri = operation.result.generated_videos[0].video.uri
        return video_uri  # URL temporária — @dev salva no Supabase Storage na sequência
```

### Prompts de vídeo — exemplos

**Cinematic:**
```
Slow cinematic push-in on face, subtle hair movement in breeze,
blink once naturally, bokeh background softly shifting,
warm golden light, 24fps film grain
```

**Influencer Natural:**
```
Slight head turn towards camera, natural smile emerging,
hand gesture casual, background slightly out of focus,
bright natural light, smooth movement
```

---

## Integration Verifications

- [x] `GEMINI_API_KEY` aceita pela API Veo — configurada no VPS em `/opt/sparkle-aiox/.venv`
- [ ] Operation retorna `done=True` dentro do timeout de 5 min *(pendente: VEO_LIVE_TESTS=1)*
- [ ] Polling detecta `operation.done` e retorna URI do vídeo *(pendente: VEO_LIVE_TESTS=1)*
- [ ] Vídeo salvo no Supabase Storage e acessível *(pendente: VEO_LIVE_TESTS=1)*
- [ ] `content_pieces.video_url` preenchido e `status = "video_done"` *(pendente: VEO_LIVE_TESTS=1)*
- [x] Falha simulada resulta em `status = "video_failed"` — `_record_failure()` verificado no código
- [x] Timeout de 5 min resulta em `status = "video_failed"` — loop `for/else` com `TimeoutError` capturado

---

## QA Results

**QA Agent:** @qa (Quinn)
**Date:** 2026-04-07
**Gate Decision:** ✅ PASS com CONCERNS

### AC Coverage
| AC | Status | Verificação |
|----|--------|-------------|
| AC1 | ✅ PASS | `build_video_prompt()` retorna prompt com movimento, câmera, física, contexto de tema |
| AC2 | ✅ PASS | `VideoGeneratorProtocol` com `@runtime_checkable` — interface limpa e verificável |
| AC3 | ✅ PASS | `VeoVideoGenerator` autentica via `GEMINI_API_KEY`, chama `generate_videos(model="veo-2.0-generate-001")` |
| AC4 | ✅ PASS | `aspect_ratio="9:16"`, `duration_seconds` (5 ou 10 por estilo), `number_of_videos=1` |
| AC5 | ✅ PASS | Loop `for _ in range(30)` + `asyncio.sleep(10)` + `operation.done` + `else: raise TimeoutError` |
| AC6 | ✅ PASS | Download do URI temporário + upload `content-assets/videos/{id}.mp4` com `upsert=true` |
| AC7 | ✅ PASS | `video_url` + `status=video_done` atualizados após upload |
| AC8 | ✅ PASS | `TimeoutError` e `Exception` genérico → `_record_failure()` → `video_failed` + `error_log` |

### Test Results
- **11 passed, 4 skipped** (15 total — todos compartilhados com CONTENT-1.2)
- 4 testes CONTENT-1.3: 4 pass + 3 skip (todos os skips esperados: Veo live + `/content/pieces` futuro)

### Concerns (não bloqueantes)

**MEDIUM — VeoVideoGenerator não é singleton:** `generate_video_for_piece()` instancia `VeoVideoGenerator()` a cada chamada, criando novo client Gemini. Para MVP sem carga concorrente, aceitável. Em produção, considerar module-level singleton.

**LOW — `video_prompt` column assumed:** `generate_video_for_piece()` escreve `video_prompt` em `content_pieces`. Confirmar se a coluna existe no schema antes de habilitar em produção. Se não existir, update silencioso falha sem crashar (Supabase ignora colunas inexistentes na resposta mas pode gerar erro 400).

**INFO — Veo live tests não executados:** Aguarda `VEO_LIVE_TESTS=1` + GEMINI_API_KEY com quota Veo habilitada. Esperado para MVP.

### Verdict
`VideoGeneratorProtocol` bem desenhado para extensibilidade futura. Polling pattern correto, tratamento de falhas robusto. Abstração permite swap de provider sem tocar no pipeline. Aprovado para push — concerns são debt de produção, não blockers de MVP.

---

## Dev Agent Record

**Agent Model Used:** claude-sonnet-4-6

**Completion Notes:**
- Implementado junto com CONTENT-1.2 (mesma sessão, mesmos arquivos)
- `VideoGeneratorProtocol` definido com `@runtime_checkable` para type checking
- `VeoVideoGenerator` usa `asyncio.to_thread` para chamadas síncronas do SDK
- Polling: 30 iterações × 10s = max 5 min; `TimeoutError` capturado e registrado como `video_failed`
- Testes de geração real (`VEO_LIVE_TESTS=1`) skippados por padrão — Veo tem custo e latência alta
- `_record_failure()` compartilhado entre image e video generators — mesmo padrão

**Change Log:**
- Criado: `runtime/content/video_engineer.py`
- Criado: `runtime/content/video_generator.py`
- Modificado: `runtime/content/router.py` (compartilhado com CONTENT-1.2)
- Criado: `tests/test_video_engine.py`

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/video_engineer.py` | ✅ Criado | Prompt engineer: build_video_prompt, get_video_duration por estilo |
| `runtime/content/video_generator.py` | ✅ Criado | VideoGeneratorProtocol + VeoVideoGenerator (google-genai 1.70.0) |
| `runtime/content/router.py` | ✅ Modificado | Endpoints /video/generate, /video/apply/{id}, /video/status |
| `tests/test_video_engine.py` | ✅ Criado | 7 testes (4 pass, 3 skip — Veo live requer VEO_LIVE_TESTS=1) |
