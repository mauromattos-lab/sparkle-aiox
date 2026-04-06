---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.3
title: "Video Prompt Engineer + Geração Kling API"
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
blocker: "KLING_ACCESS_KEY + KLING_SECRET_KEY — Mauro obtém em klingai.com → API"
---

# Story 1.3 — Video Prompt Engineer + Geração Kling API

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

**Estado atual:** Nenhuma integração com Kling API existe no Runtime. Higgsfield (usado anteriormente) não tem mais assinatura.

**Estado alvo:** `video_engineer.py` gera prompt de movimento a partir da imagem + estilo; `video_generator.py` chama Kling API (image-to-video); vídeo 9:16 5-10s salvo no Supabase Storage; status avança `image_done` → `video_generating` → `video_done`.

**Arquitetura de abstração:** `video_generator.py` implementa `VideoGeneratorProtocol` para permitir swap futuro para ComfyUI+RunPod sem alterar o pipeline.

**⚠️ BLOCKER:** `KLING_ACCESS_KEY` e `KLING_SECRET_KEY` precisam estar em variáveis de ambiente antes dos testes.

---

## Acceptance Criteria

- [ ] **AC1** — `video_engineer.py` recebe imagem gerada + estilo e retorna prompt de vídeo descrevendo: movimento da personagem, câmera, física do ambiente, duração e aspect ratio
- [ ] **AC2** — `VideoGeneratorProtocol` definido com interface: `async def generate(image_url, prompt, style) -> str`
- [ ] **AC3** — `KlingVideoGenerator` implementa o protocolo: autentica via JWT (KLING_ACCESS_KEY + KLING_SECRET_KEY), chama `POST https://api.kling.ai/v1/videos/image2video`
- [ ] **AC4** — Parâmetros obrigatórios na chamada Kling: `model_name: "kling-v1-5"`, `aspect_ratio: "9:16"`, `duration: "5"` (ou 10 para cinematic)
- [ ] **AC5** — Kling retorna job ID — `video_generator.py` faz polling até job completar (max 5 min com retry)
- [ ] **AC6** — Vídeo gerado baixado e salvo no Supabase Storage em `content-assets/videos/{content_piece_id}.mp4`
- [ ] **AC7** — `content_pieces.video_url` atualizado; `status` avança para `video_done`
- [ ] **AC8** — Falha na API ou timeout atualiza `status = 'video_failed'` e registra em `error_log` — pipeline continua para outras peças

---

## Dev Notes

### Autenticação Kling (JWT)
```python
import jwt, time

def get_kling_jwt(access_key: str, secret_key: str) -> str:
    payload = {
        "iss": access_key,
        "exp": int(time.time()) + 1800,
        "nbf": int(time.time()) - 5
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")
```

### VideoGeneratorProtocol
```python
from typing import Protocol

class VideoGeneratorProtocol(Protocol):
    async def generate(self, image_url: str, prompt: str, style: str) -> str:
        """Returns: Storage path do vídeo gerado"""
        ...
```

### Chamada Kling + polling
```python
async def generate(self, image_url: str, prompt: str, style: str) -> str:
    token = get_kling_jwt(self.access_key, self.secret_key)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Criar job
    resp = await httpx.post(
        "https://api.kling.ai/v1/videos/image2video",
        headers=headers,
        json={
            "model_name": "kling-v1-5",
            "image_url": image_url,
            "prompt": prompt,
            "negative_prompt": "blurry, distorted, inconsistent, low quality",
            "duration": "10" if style == "cinematic" else "5",
            "aspect_ratio": "9:16"
        }
    )
    task_id = resp.json()["data"]["task_id"]
    
    # Polling até completar (max 5 min)
    for _ in range(60):
        await asyncio.sleep(5)
        status_resp = await httpx.get(
            f"https://api.kling.ai/v1/videos/image2video/{task_id}",
            headers=headers
        )
        task = status_resp.json()["data"]
        if task["task_status"] == "succeed":
            return task["task_result"]["videos"][0]["url"]
        if task["task_status"] == "failed":
            raise RuntimeError(f"Kling job failed: {task.get('task_status_msg')}")
    
    raise TimeoutError("Kling job timeout após 5 minutos")
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

- [ ] JWT gerado com KLING_ACCESS_KEY + KLING_SECRET_KEY é aceito pela API (status 200)
- [ ] Job criado retorna `task_id` válido
- [ ] Polling detecta `task_status == "succeed"` e retorna URL do vídeo
- [ ] Vídeo salvo no Supabase Storage e acessível
- [ ] `content_pieces.video_url` preenchido e `status = "video_done"`
- [ ] Falha simulada (key inválida) resulta em `status = "video_failed"` sem crashar o processo

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/video_engineer.py` | Criar | Prompt engineer para movimento/câmera por estilo |
| `runtime/content/video_generator.py` | Criar | VideoGeneratorProtocol + KlingVideoGenerator |
| `tests/test_video_generator.py` | Criar | Testes: auth JWT, polling, timeout, failure handling |
