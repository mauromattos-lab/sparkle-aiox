"""
Brain Namespace Resolution — B3-05.

Determines the appropriate namespace for a brain chunk based on its
source URL, file type, and metadata. Namespaces group related knowledge
for faster retrieval and organizational clarity.

Default namespaces:
  - youtube       : YouTube transcripts
  - web           : Generic web page content
  - file_pdf      : Uploaded PDF documents
  - file_csv      : Uploaded CSV data
  - file_text     : Uploaded .txt / .md files
  - conversation  : Conversation digests / summaries
  - client_dna    : Client DNA extractions
  - insight       : Brain insights / synthesis
  - general       : Fallback for anything unclassified
"""
from __future__ import annotations

import re
from typing import Any


# ── Source-type mapping ───────────────────────────────────────────────────────

_SOURCE_TYPE_MAP: dict[str, str] = {
    "youtube": "youtube",
    "web_url": "web",
    "file_upload": "file",
    "weekly_digest": "conversation",
    "conversation_summary": "conversation",
    "client_dna": "client_dna",
    "insight": "insight",
    "narrative": "insight",
}

# File extension refinement (used when source_type is file_upload)
_FILE_EXT_MAP: dict[str, str] = {
    ".pdf": "file_pdf",
    ".csv": "file_csv",
    ".txt": "file_text",
    ".md": "file_text",
}


def resolve_namespace(
    source_url: str | None = None,
    file_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Resolve the namespace for a brain chunk.

    Priority:
      1. Explicit namespace in metadata (if provided)
      2. Source type mapping (youtube, web_url, file_upload, etc.)
      3. File extension refinement for file uploads
      4. URL-based detection (YouTube patterns)
      5. Fallback to 'general'

    Args:
        source_url: The URL the content was ingested from (if any).
        file_type: File extension (e.g. ".pdf") or source_type string.
        metadata: chunk_metadata dict — may contain 'namespace', 'source_type',
                  'file_extension', etc.

    Returns:
        A namespace string (lowercase, no spaces).
    """
    meta = metadata or {}

    # 1. Explicit namespace override
    explicit = meta.get("namespace")
    if explicit and isinstance(explicit, str) and explicit.strip():
        return _normalize(explicit)

    # 2. Source type from metadata
    source_type = meta.get("source_type") or file_type or ""
    source_type = source_type.lower().strip()

    mapped = _SOURCE_TYPE_MAP.get(source_type)
    if mapped:
        # 3. Refine file uploads by extension
        if mapped == "file":
            ext = meta.get("file_extension", "")
            return _FILE_EXT_MAP.get(ext, "file_text")
        return mapped

    # 4. URL-based detection
    if source_url:
        url = source_url.lower()
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        # Could add more URL-based rules here

    # 5. File type string as extension
    if file_type and file_type.startswith("."):
        return _FILE_EXT_MAP.get(file_type.lower(), "file_text")

    return "general"


def _normalize(ns: str) -> str:
    """Normalize a namespace string: lowercase, replace spaces/special chars."""
    ns = ns.lower().strip()
    ns = re.sub(r"[^a-z0-9_-]", "_", ns)
    ns = re.sub(r"_+", "_", ns).strip("_")
    return ns or "general"
