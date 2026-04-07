"""
brain ingest-url — Ingere conteúdo de URL no Brain.

Suporta:
  - YouTube: extrai transcrição via youtube-transcript-api (sem baixar vídeo)
  - URLs web: extrai texto via httpx + remoção de HTML básico
  - Chunking automático para conteúdo longo (>1500 chars por chunk)

Endpoint: POST /brain/ingest-url
Body: {"url": "...", "title": "...", "source_agent": "mauro", "client_id": null}
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from runtime.brain.isolation import get_brain_owner_for_ingest
from runtime.brain.namespace import resolve_namespace
from runtime.db import supabase

router = APIRouter()

# Dedup stats tracked per-request
_DEDUP_SKIPPED = "dedup_skipped"


class IngestUrlRequest(BaseModel):
    url: str
    title: Optional[str] = ""
    source_agent: Optional[str] = "mauro"
    client_id: Optional[str] = None
    persona: Optional[str] = "mauro"  # para qual persona vai o conhecimento


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def _get_youtube_transcript(url: str) -> tuple[str, str]:
    """Extrai transcrição do YouTube. Retorna (texto, titulo).

    Tenta youtube-transcript-api primeiro (rápido, grátis).
    Se falhar (IP bloqueado em cloud), usa Apify como fallback.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Não foi possível extrair video_id de: {url}")

    # Tentativa 1: youtube-transcript-api (direto, grátis)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        def _fetch() -> str:
            api = YouTubeTranscriptApi()
            for lang in (["pt", "pt-BR"], ["en"]):
                try:
                    fetched = api.fetch(video_id, languages=lang)
                    return " ".join(s.text for s in fetched)
                except Exception:
                    continue
            fetched = api.fetch(video_id)
            return " ".join(s.text for s in fetched)

        text = await asyncio.to_thread(_fetch)
        title = f"YouTube: {video_id}"
        return text, title
    except Exception as direct_err:
        print(f"[ingest_url] youtube-transcript-api falhou: {direct_err}")

    # Tentativa 2: Apify YouTube Transcript (contorna bloqueio de IP)
    apify_token = os.getenv("APIFY_API_TOKEN")
    if apify_token:
        try:
            text, title = await _get_youtube_via_apify(video_id, url, apify_token)
            return text, title
        except Exception as apify_err:
            print(f"[ingest_url] Apify fallback falhou: {apify_err}")

    raise ValueError(f"Transcrição não disponível para {video_id} (direto + Apify falharam)")


async def _get_youtube_via_apify(video_id: str, url: str, token: str) -> tuple[str, str]:
    """Extrai transcrição do YouTube via Apify pintostudio/youtube-transcript-scraper."""
    async with httpx.AsyncClient() as client:
        run_resp = await client.post(
            f"https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/run-sync-get-dataset-items?token={token}",
            headers={"Authorization": f"Bearer {token}"},
            json={"videoUrl": url},
            timeout=120.0,
        )
        run_resp.raise_for_status()
        items = run_resp.json()

        if items and len(items) > 0:
            item = items[0]
            # O actor retorna {"data": [{"start": "0.0", "dur": "3.0", "text": "..."}]}
            segments = item.get("data", [])
            if isinstance(segments, list) and segments:
                text = " ".join(seg.get("text", "") for seg in segments if seg.get("text"))
                if text and len(text) > 100:
                    title = f"YouTube: {video_id}"
                    return text, title

    raise ValueError(f"Apify não retornou conteúdo útil para {video_id}")


async def _get_url_content(url: str) -> tuple[str, str]:
    """Extrai conteúdo de URL genérica."""
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        resp = await client.get(url, timeout=15.0, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        if "pdf" in content_type:
            raise ValueError("PDFs binários não suportados via URL — converta para texto primeiro")

        text = resp.text
        # Remove HTML básico
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Extrai título da página
        title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else url[:80]

        return text, title


def _chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Divide texto longo em chunks com overlap para preservar contexto."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # Tenta quebrar em fim de frase para não cortar no meio de uma ideia
        last_period = chunk.rfind('. ')
        if last_period > chunk_size * 0.7:
            chunk = chunk[:last_period + 1]
            end = start + last_period + 1
        chunks.append(chunk)
        start = end - overlap
    return chunks


async def _get_embedding(text: str) -> list[float] | None:
    """Gera embedding via OpenAI text-embedding-3-small. Retorna None se sem API key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": text[:8000]},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception:
        return None


@router.post("/ingest-url")
async def ingest_url(req: IngestUrlRequest):
    """
    Ingere conteúdo de URL no Brain.
    Suporta YouTube (transcrição automática) e URLs web.
    Realiza chunking automático e gera embeddings vetoriais quando OPENAI_API_KEY disponível.
    """
    try:
        # 1. Extrair conteúdo conforme tipo de URL
        if _is_youtube(req.url):
            raw_text, auto_title = await _get_youtube_transcript(req.url)
            source_type = "youtube"
        else:
            raw_text, auto_title = await _get_url_content(req.url)
            source_type = "web_url"

        title = req.title or auto_title
        client_id = req.client_id  # None = sparkle-internal

        if not raw_text or len(raw_text) < 50:
            return {"status": "error", "message": "Conteúdo extraído muito curto ou vazio"}

        # 2. Chunking
        chunks = _chunk_text(raw_text)

        # 3. Inserir cada chunk no Brain com embedding (com dedup semantica)
        from runtime.brain.dedup import check_duplicate_chunk, confirm_existing_chunk

        inserted = 0
        duplicates_confirmed = 0
        chunk_ids = []

        for i, chunk in enumerate(chunks):
            embedding = await _get_embedding(chunk)

            # Dedup: verifica se chunk similar ja existe
            if embedding:
                existing = await check_duplicate_chunk(embedding)
                if existing:
                    print(
                        f"[brain/dedup] chunk similar encontrado "
                        f"(similarity={existing['similarity']:.4f}), "
                        f"confirmando existente {existing['id']}"
                    )
                    await confirm_existing_chunk(existing["id"])
                    duplicates_confirmed += 1
                    continue

            chunk_title = (
                f"{title} (chunk {i+1}/{len(chunks)})" if len(chunks) > 1 else title
            )
            # B1-03: set brain_owner based on source_agent + client_id
            brain_owner = get_brain_owner_for_ingest(
                req.source_agent or "mauro", client_id,
            )
            # B3-05: resolve namespace from source
            chunk_meta = {
                "source_url": req.url,
                "source_agent": req.source_agent,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source_type": source_type,
            }
            namespace = resolve_namespace(
                source_url=req.url,
                file_type=source_type,
                metadata=chunk_meta,
            )
            row: dict = {
                "raw_content": chunk,
                "source_type": source_type,
                "source_title": chunk_title,
                "pipeline_type": "mauro",
                "brain_owner": brain_owner,
                "namespace": namespace,
                "chunk_metadata": chunk_meta,
            }
            if client_id:
                row["client_id"] = client_id
            if embedding:
                row["embedding"] = embedding

            try:
                result = await asyncio.to_thread(
                    lambda r=row: supabase.table("brain_chunks").insert(r).execute()
                )
                if result.data:
                    chunk_ids.append(result.data[0]["id"])
                    inserted += 1
            except Exception as e:
                print(f"[brain/ingest-url] falha chunk {i}: {e}")

        return {
            "status": "ok",
            "url": req.url,
            "title": title,
            "source_type": source_type,
            "chunks_total": len(chunks),
            "chunks_inserted": inserted,
            "duplicates_confirmed": duplicates_confirmed,
            "chunk_ids": chunk_ids,
            "text_length": len(raw_text),
            "message": (
                f"'{title}' ingerido no Brain — {inserted} chunks novos, "
                f"{duplicates_confirmed} duplicatas confirmadas"
            ),
        }

    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Erro inesperado: {str(e)[:200]}"}
