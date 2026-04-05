"""
Handler scrape_instagram — ONB-2: Scrape de perfil Instagram via Apify.

Extrai: bio, posts recentes (últimos 10), hashtags frequentes, horários de postagem.
Ingere dados no Brain como chunks com source_type=instagram.

ACs: 2.1, 2.2, 2.3, 2.4

Fallback: se APIFY_API_TOKEN não estiver configurado ou o Actor falhar,
loga warning e retorna graciosamente (não bloqueia o pipeline).
"""
from __future__ import annotations

import asyncio
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

import httpx

from runtime.db import supabase
from runtime.brain.embedding import get_embedding
from runtime.brain.isolation import get_brain_owner_for_ingest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_hashtags(text: str) -> list[str]:
    """Extrai hashtags de um texto."""
    return re.findall(r"#\w+", text.lower())


def _normalize_instagram_url(url: str) -> str:
    """Normaliza URL do Instagram para garantir formato correto."""
    url = url.strip().rstrip("/")
    if url.startswith("@"):
        url = "https://www.instagram.com/" + url[1:]
    elif not url.startswith("http"):
        url = "https://www.instagram.com/" + url.lstrip("/")
    return url


async def _scrape_via_apify(instagram_url: str, apify_token: str) -> dict:
    """
    Scrapes Instagram profile via Apify apify/instagram-profile-scraper.

    Returns raw Actor output dict.
    """
    normalized_url = _normalize_instagram_url(instagram_url)

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"https://api.apify.com/v2/acts/apify~instagram-profile-scraper/run-sync-get-dataset-items",
            params={"token": apify_token},
            json={
                "directUrls": [normalized_url],
                "resultsType": "posts",
                "resultsLimit": 10,
            },
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


def _build_instagram_chunks(profile_data: list[dict], instagram_url: str) -> list[str]:
    """
    Transforma dados brutos do Apify em chunks de texto para ingestão no Brain.

    Gera:
    - 1 chunk com bio + stats
    - 1 chunk com resumo dos posts (captions + hashtags)
    - 1 chunk com análise de hashtags frequentes e horários
    """
    chunks = []
    all_hashtags: list[str] = []
    post_hours: list[int] = []
    captions: list[str] = []

    # Extrai dados do primeiro item (perfil)
    profile = profile_data[0] if profile_data else {}

    # Chunk 1: Bio e stats do perfil
    bio = profile.get("biography", "") or profile.get("bio", "") or ""
    username = profile.get("username", "") or profile.get("handle", "")
    followers = profile.get("followersCount", 0) or profile.get("followers", 0)
    full_name = profile.get("fullName", "") or profile.get("name", "")

    if bio or username:
        bio_chunk = f"Instagram: @{username}\n"
        if full_name:
            bio_chunk += f"Nome: {full_name}\n"
        if bio:
            bio_chunk += f"Bio: {bio}\n"
        if followers:
            bio_chunk += f"Seguidores: {followers:,}\n"
        chunks.append(bio_chunk.strip())

    # Processa posts
    posts = profile.get("latestPosts", []) or profile.get("posts", []) or []
    # Apify às vezes retorna lista de itens separados
    if not posts and len(profile_data) > 1:
        posts = profile_data[1:]

    for post in posts[:10]:
        caption = post.get("caption", "") or post.get("text", "") or ""
        if caption:
            captions.append(caption[:300])
            all_hashtags.extend(_extract_hashtags(caption))

        # Horário do post
        timestamp = post.get("timestamp", "") or post.get("takenAt", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                post_hours.append(dt.hour)
            except Exception:
                pass

    # Chunk 2: Captions dos posts recentes
    if captions:
        posts_text = "Posts recentes do Instagram:\n" + "\n---\n".join(captions[:5])
        chunks.append(posts_text)

    # Chunk 3: Análise de hashtags e horários de postagem
    analytics_lines = []
    if all_hashtags:
        top_hashtags = [h for h, _ in Counter(all_hashtags).most_common(15)]
        analytics_lines.append(f"Hashtags mais usadas: {', '.join(top_hashtags)}")

    if post_hours:
        avg_hour = sum(post_hours) // len(post_hours)
        hour_counter = Counter(post_hours)
        peak_hour = hour_counter.most_common(1)[0][0] if hour_counter else avg_hour
        analytics_lines.append(
            f"Horário médio de postagem: {avg_hour}h | Pico: {peak_hour}h"
        )

    if analytics_lines:
        chunks.append("Análise Instagram:\n" + "\n".join(analytics_lines))

    return chunks


async def handle_scrape_instagram(task: dict) -> dict:
    """
    Scrape de perfil Instagram via Apify.

    Payload esperado:
    {
        "client_id": "...",
        "instagram_url": "https://www.instagram.com/exemplo"
    }

    Returns:
        dict com chunks_inserted, skipped, error (se houver)
    """
    payload = task.get("payload", {})
    client_id: Optional[str] = payload.get("client_id") or task.get("client_id")
    instagram_url: Optional[str] = payload.get("instagram_url", "").strip()

    # AC-2.4: se instagram_url vazio, pula silenciosamente
    if not instagram_url:
        print(f"[scrape_instagram] instagram_url vazio — skip (client_id={client_id})")
        return {"skipped": True, "reason": "instagram_url nao fornecido", "chunks_inserted": 0}

    apify_token = os.getenv("APIFY_API_TOKEN", "")
    if not apify_token:
        print("[scrape_instagram] APIFY_API_TOKEN nao configurado — skip")
        return {"skipped": True, "reason": "APIFY_API_TOKEN nao configurado", "chunks_inserted": 0}

    # AC-2.1: scrape via Apify
    try:
        raw_data = await _scrape_via_apify(instagram_url, apify_token)
    except Exception as e:
        print(f"[scrape_instagram] WARN: Apify falhou para {instagram_url}: {e}")
        return {"skipped": False, "error": str(e)[:200], "chunks_inserted": 0}

    if not raw_data:
        print(f"[scrape_instagram] Apify retornou vazio para {instagram_url}")
        return {"skipped": True, "reason": "Apify sem dados", "chunks_inserted": 0}

    # AC-2.2: build chunks from raw data
    try:
        text_chunks = _build_instagram_chunks(raw_data, instagram_url)
    except Exception as e:
        print(f"[scrape_instagram] WARN: falha ao processar dados Apify: {e}")
        return {"skipped": False, "error": str(e)[:200], "chunks_inserted": 0}

    if not text_chunks:
        return {"skipped": True, "reason": "nenhum conteudo util extraido", "chunks_inserted": 0}

    # AC-2.3: ingest chunks into Brain with source_type=instagram
    # Save raw ingestion first
    now_ts = _now()
    raw_id = None
    try:
        raw_row = {
            "source_type": "instagram",
            "source_ref": instagram_url,
            "title": f"Instagram — {instagram_url}",
            "raw_content": "\n\n".join(text_chunks),
            "pipeline_type": "zenya",
            "metadata": {"client_id": client_id, "source_agent": "scrape_instagram"},
            "status": "processing",
        }
        if client_id:
            raw_row["client_id"] = client_id
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_raw_ingestions").insert(raw_row).execute()
        )
        if result.data:
            raw_id = result.data[0]["id"]
    except Exception as e:
        print(f"[scrape_instagram] WARN: falha ao salvar raw_ingestion: {e}")

    # Insert brain_chunks
    inserted_ids: list[str] = []
    for i, chunk_text in enumerate(text_chunks):
        try:
            embedding = await get_embedding(chunk_text)
            brain_owner = get_brain_owner_for_ingest("zenya", client_id)

            row: dict = {
                "raw_content": chunk_text,
                "source_type": "instagram",
                "source_title": f"Instagram — {instagram_url} (chunk {i+1}/{len(text_chunks)})",
                "pipeline_type": "zenya",
                "brain_owner": brain_owner,
                "chunk_metadata": {
                    "source_url": instagram_url,
                    "source_agent": "scrape_instagram",
                    "chunk_index": i,
                    "total_chunks": len(text_chunks),
                    "raw_ingestion_id": str(raw_id) if raw_id else None,
                },
            }
            if client_id:
                row["client_id"] = client_id
            if embedding:
                row["embedding"] = embedding
            if raw_id:
                row["raw_ingestion_id"] = raw_id

            result = await asyncio.to_thread(
                lambda r=row: supabase.table("brain_chunks").insert(r).execute()
            )
            if result.data:
                inserted_ids.append(result.data[0]["id"])
        except Exception as e:
            print(f"[scrape_instagram] WARN: falha ao inserir chunk {i}: {e}")

    # Update raw status
    if raw_id:
        try:
            await asyncio.to_thread(
                lambda: supabase.table("brain_raw_ingestions")
                .update({
                    "status": "completed" if inserted_ids else "failed",
                    "chunks_generated": len(inserted_ids),
                })
                .eq("id", raw_id)
                .execute()
            )
        except Exception:
            pass

    print(
        f"[scrape_instagram] {len(inserted_ids)} chunks inseridos "
        f"para client_id={str(client_id)[:12]}..."
    )
    return {
        "skipped": False,
        "chunks_inserted": len(inserted_ids),
        "chunk_ids": [str(cid) for cid in inserted_ids],
        "raw_ingestion_id": str(raw_id) if raw_id else None,
        "instagram_url": instagram_url,
    }
