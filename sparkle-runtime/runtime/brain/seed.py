"""
C2-B1: Brain Namespace Seed Script.

Idempotent script that reads source files, chunks them by section/paragraph,
and ingests into the brain with the correct brain_owner namespace.

Supports three namespaces:
  - mauro-personal: Mauro's vision, decisions, session summaries
  - sparkle-lore:   Zenya character IP (lore, SOUL, character bible)
  - sparkle-ops:    Operational rules, pipeline, feedback rules

Usage:
  python -m runtime.brain.seed                        # seed all namespaces
  python -m runtime.brain.seed --namespace mauro-personal
  python -m runtime.brain.seed --namespace sparkle-lore
  python -m runtime.brain.seed --namespace sparkle-ops

Idempotency: uses SHA-256 hash of chunk content to detect duplicates.
Running twice produces zero new inserts.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Namespace -> source file mappings ──────────────────────────────────────

# Base paths — resolved relative to this file's location at runtime.
# The script can run from VPS (/opt/sparkle-runtime/) or local dev.
_RUNTIME_ROOT = Path(__file__).resolve().parent.parent.parent  # sparkle-runtime/
_PROJECT_ROOT = _RUNTIME_ROOT.parent  # Sparkle AIOX/

# Memory files live in the Claude project-specific memory folder on dev,
# but on VPS they are committed under the repo. We check both locations.
_MEMORY_CANDIDATES = [
    Path.home() / ".claude" / "projects" / "C--Users-Mauro-Desktop-Sparkle-AIOX" / "memory",
    _PROJECT_ROOT / "memory",
    _RUNTIME_ROOT / "memory",
]


def _find_memory_dir() -> Path | None:
    for candidate in _MEMORY_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


NAMESPACE_SOURCES: dict[str, list[dict[str, Any]]] = {
    "mauro-personal": [
        # Memory files with Mauro's vision and decisions
        {"path_key": "memory", "file": "project_sparkle_vision_complete.md", "label": "Sparkle Vision Complete"},
        {"path_key": "memory", "file": "session_2026_03_31_vision_deep.md", "label": "Vision Deep Session"},
        {"path_key": "memory", "file": "project_sparkle_longterm_vision.md", "label": "Long-term Vision"},
        {"path_key": "memory", "file": "session_aria_elicitation_2026_03_31.md", "label": "Aria Elicitation Session"},
    ],
    "sparkle-lore": [
        {"path_key": "docs", "file": "docs/zenya/zenya-lore-canonical.md", "label": "Zenya Lore Canonical"},
        {"path_key": "docs", "file": "docs/zenya/SOUL.md", "label": "Zenya SOUL"},
        {"path_key": "docs", "file": "docs/zenya/LORE.md", "label": "Zenya LORE"},
    ],
    "sparkle-ops": [
        {"path_key": "docs", "file": "docs/operations/sparkle-os-processes.md", "label": "Sparkle OS Processes"},
        {"path_key": "docs", "file": "docs/operations/agent-toolkit-standard.md", "label": "Agent Toolkit Standard"},
        # Key feedback rules from memory
        {"path_key": "memory", "file": "feedback_7_rules_sparkle_os.md", "label": "7 Rules Sparkle OS"},
        {"path_key": "memory", "file": "feedback_mandatory_process.md", "label": "Mandatory Process"},
        {"path_key": "memory", "file": "feedback_parallel_operations.md", "label": "Parallel Operations"},
        {"path_key": "memory", "file": "feedback_aios_pipeline_mandatory.md", "label": "AIOS Pipeline Mandatory"},
        {"path_key": "memory", "file": "feedback_excellence_over_speed.md", "label": "Excellence Over Speed"},
        {"path_key": "memory", "file": "feedback_qa_before_activate.md", "label": "QA Before Activate"},
    ],
}


def _resolve_file_path(source: dict) -> Path | None:
    """Resolve a source dict to an actual file path."""
    if source["path_key"] == "memory":
        mem_dir = _find_memory_dir()
        if mem_dir:
            p = mem_dir / source["file"]
            if p.exists():
                return p
    elif source["path_key"] == "docs":
        p = _PROJECT_ROOT / source["file"]
        if p.exists():
            return p
    return None


# ── Chunking ───────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_MIN_CHUNK_CHARS = 80  # skip very short chunks (headers only, etc.)


def chunk_markdown(text: str, source_label: str) -> list[dict]:
    """Split markdown text into chunks by heading sections.

    Each chunk contains the heading and its body text.
    Very short chunks (< _MIN_CHUNK_CHARS body) are merged with the next.
    """
    chunks: list[dict] = []
    headings = list(_HEADING_RE.finditer(text))

    if not headings:
        # No headings — treat entire file as one chunk
        content = text.strip()
        if len(content) >= _MIN_CHUNK_CHARS:
            chunks.append({
                "content": content,
                "section": source_label,
                "content_hash": _hash(content),
            })
        return chunks

    # Add preamble (text before first heading) if substantial
    preamble = text[:headings[0].start()].strip()
    if len(preamble) >= _MIN_CHUNK_CHARS:
        chunks.append({
            "content": preamble,
            "section": f"{source_label} (preamble)",
            "content_hash": _hash(preamble),
        })

    for i, match in enumerate(headings):
        heading_text = match.group(2).strip()
        start = match.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()

        if len(body) < _MIN_CHUNK_CHARS:
            # Merge into next chunk or skip
            continue

        chunks.append({
            "content": body,
            "section": f"{source_label} > {heading_text}",
            "content_hash": _hash(body),
        })

    return chunks


def _hash(text: str) -> str:
    """SHA-256 hex digest of the chunk content (for dedup)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Deduplication via content hash ─────────────────────────────────────────

async def _get_existing_hashes(namespace: str) -> set[str]:
    """Fetch all content_hash values already in brain_chunks for this namespace."""
    from runtime.db import supabase

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("chunk_metadata->content_hash")
            .eq("brain_owner", namespace)
            .execute()
        )
        hashes = set()
        for row in (result.data or []):
            h = row.get("content_hash")
            if h:
                hashes.add(h)
        return hashes
    except Exception as e:
        logger.warning("[brain/seed] failed to fetch existing hashes for %s: %s", namespace, e)
        return set()


# ── Ingest a single chunk ──────────────────────────────────────────────────

async def _ingest_chunk(
    content: str,
    namespace: str,
    section: str,
    content_hash: str,
    source_label: str,
) -> bool:
    """Insert a single chunk into brain_chunks. Returns True if inserted."""
    from runtime.brain.embedding import get_embedding
    from runtime.db import supabase

    embedding = await get_embedding(content)

    row = {
        "raw_content": content,
        "source_type": "seed",
        "source_title": source_label,
        "pipeline_type": "mauro",
        "brain_owner": namespace,
        "chunk_metadata": {
            "source_agent": "seed",
            "ingest_type": "seed",
            "section": section,
            "content_hash": content_hash,
        },
    }
    if embedding:
        row["embedding"] = embedding

    try:
        await asyncio.to_thread(
            lambda: supabase.table("brain_chunks").insert(row).execute()
        )
        return True
    except Exception as e:
        logger.error("[brain/seed] failed to insert chunk '%s': %s", section[:60], e)
        return False


# ── Seed a single namespace ────────────────────────────────────────────────

async def seed_namespace(namespace: str) -> dict:
    """Seed all source files for a namespace. Returns stats dict."""
    sources = NAMESPACE_SOURCES.get(namespace)
    if not sources:
        logger.error("[brain/seed] unknown namespace: %s", namespace)
        return {"namespace": namespace, "error": f"unknown namespace: {namespace}"}

    existing_hashes = await _get_existing_hashes(namespace)

    total_chunks = 0
    already_existed = 0
    newly_ingested = 0
    files_processed = 0
    files_missing = 0

    for source in sources:
        file_path = _resolve_file_path(source)
        if not file_path:
            logger.warning("[brain/seed] file not found: %s", source["file"])
            files_missing += 1
            continue

        text = file_path.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_markdown(text, source["label"])
        files_processed += 1

        for chunk in chunks:
            total_chunks += 1
            if chunk["content_hash"] in existing_hashes:
                already_existed += 1
                continue

            ok = await _ingest_chunk(
                content=chunk["content"],
                namespace=namespace,
                section=chunk["section"],
                content_hash=chunk["content_hash"],
                source_label=source["label"],
            )
            if ok:
                newly_ingested += 1
                existing_hashes.add(chunk["content_hash"])

    stats = {
        "namespace": namespace,
        "files_processed": files_processed,
        "files_missing": files_missing,
        "total_chunks": total_chunks,
        "already_existed": already_existed,
        "newly_ingested": newly_ingested,
    }

    logger.info(
        "[brain/seed] Ingested %d chunks in %s (%d already existed, %d new)",
        total_chunks,
        namespace,
        already_existed,
        newly_ingested,
    )
    print(
        f"Ingested {total_chunks} chunks in {namespace} "
        f"({already_existed} already existed, {newly_ingested} new)"
    )

    return stats


# ── Main entry point ───────────────────────────────────────────────────────

async def seed_all(namespaces: list[str] | None = None) -> list[dict]:
    """Seed one or more namespaces. Defaults to all three."""
    targets = namespaces or list(NAMESPACE_SOURCES.keys())
    results = []
    for ns in targets:
        result = await seed_namespace(ns)
        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Brain Namespace Seed (C2-B1)")
    parser.add_argument(
        "--namespace",
        choices=list(NAMESPACE_SOURCES.keys()),
        default=None,
        help="Seed only this namespace (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    namespaces = [args.namespace] if args.namespace else None
    results = asyncio.run(seed_all(namespaces))

    # Summary
    print("\n--- Seed Summary ---")
    for r in results:
        if "error" in r:
            print(f"  {r['namespace']}: ERROR — {r['error']}")
        else:
            print(
                f"  {r['namespace']}: "
                f"{r['newly_ingested']} new, "
                f"{r['already_existed']} existing, "
                f"{r['files_processed']} files "
                f"({r['files_missing']} missing)"
            )


if __name__ == "__main__":
    # Add parent dirs to sys.path so `runtime.*` imports work
    _this = Path(__file__).resolve()
    _runtime_pkg = _this.parent.parent.parent  # sparkle-runtime/
    if str(_runtime_pkg) not in sys.path:
        sys.path.insert(0, str(_runtime_pkg))
    main()
