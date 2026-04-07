---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.3
title: "Video Prompt Engineer + Geração Veo (Google Gemini)"
status: TODO
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

- [ ] **AC1** — `video_engineer.py` recebe imagem gerada + estilo e retorna prompt de vídeo descrevendo: movimento da personagem, câmera, física do ambiente, duração e aspect ratio
- [ ] **AC2** — `VideoGeneratorProtocol` definido com interface: `async def generate(image_url, prompt, style) -> str`
- [ ] **AC3** — `VeoVideoGenerator` implementa o protocolo: autentica via `GEMINI_API_KEY` (google-genai SDK), chama `client.aio.models.generate_videos(model="veo-2.0-generate-001", ...)`
- [ ] **AC4** — Parâmetros obrigatórios na chamada Veo: `aspect_ratio: "9:16"`, `duration_seconds: 5` (ou 10 para cinematic), `number_of_videos: 1`
- [ ] **AC5** — Veo retorna operation — `video_generator.py` faz polling via `operation.done` até completar (max 5 min com retry)
- [ ] **AC6** — Vídeo gerado baixado e salvo no Supabase Storage em `content-assets/videos/{content_piece_id}.mp4`
- [ ] **AC7** — `content_pieces.video_url` atualizado; `status` avança para `video_done`
- [ ] **AC8** — Falha na API ou timeout atualiza `status = 'video_failed'` e registra em `error_log` — pipeline continua para outras peças

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

- [ ] `GEMINI_API_KEY` aceita pela API Veo (operation criada sem erro)
- [ ] Operation retorna `done=True` dentro do timeout de 5 min
- [ ] Polling detecta `operation.done` e retorna URI do vídeo
- [ ] Vídeo salvo no Supabase Storage e acessível
- [ ] `content_pieces.video_url` preenchido e `status = "video_done"`
- [ ] Falha simulada (key inválida) resulta em `status = "video_failed"` sem crashar o processo
- [ ] Timeout de 5 min resulta em `status = "video_failed"` com mensagem clara

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/video_engineer.py` | Criar | Prompt engineer para movimento/câmera por estilo |
| `runtime/content/video_generator.py` | Criar | VideoGeneratorProtocol + VeoVideoGenerator (google-genai SDK) |
| `tests/test_video_generator.py` | Criar | Testes: auth API key, polling operation, timeout, failure handling |
