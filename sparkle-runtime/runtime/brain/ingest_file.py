"""
brain ingest-file — Ingere arquivos (PDF, texto, markdown, CSV) no Brain.

Suporta:
  - .txt, .md: leitura direta como string
  - .pdf: extração de texto via PyPDF2
  - .csv: conversão para texto estruturado

Endpoint: POST /brain/ingest-file
Body: multipart/form-data com UploadFile + campos opcionais
"""
from __future__ import annotations

import asyncio
import csv
import io
import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from runtime.brain.ingest_url import _chunk_text, _get_embedding
from runtime.db import supabase

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".csv"}


def _get_extension(filename: str) -> str:
    """Retorna extensão do arquivo em lowercase."""
    return os.path.splitext(filename or "")[-1].lower()


def _extract_text_plain(content: bytes) -> str:
    """Extrai texto de arquivos .txt e .md."""
    return content.decode("utf-8", errors="replace")


def _extract_text_pdf(content: bytes) -> str:
    """Extrai texto de PDF via PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PyPDF2 não instalado no servidor. Adicione PyPDF2 ao requirements.txt.",
        )

    reader = PdfReader(io.BytesIO(content))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)
    return "\n\n".join(pages_text)


def _extract_text_csv(content: bytes) -> str:
    """Converte CSV para texto estruturado legível."""
    text_content = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)
    if not rows:
        return ""

    # Usa primeira linha como header
    header = rows[0]
    lines = []
    for row in rows[1:]:
        parts = []
        for i, val in enumerate(row):
            col_name = header[i] if i < len(header) else f"col_{i}"
            parts.append(f"{col_name}: {val}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


EXTRACTORS = {
    ".txt": _extract_text_plain,
    ".md": _extract_text_plain,
    ".pdf": _extract_text_pdf,
    ".csv": _extract_text_csv,
}


@router.post("/ingest-file")
async def ingest_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    source_agent: Optional[str] = Form(default="mauro"),
    client_id: Optional[str] = Form(default=None),
    persona: Optional[str] = Form(default="mauro"),
):
    """
    Ingere arquivo no Brain via upload.
    Suporta .txt, .md, .pdf, .csv.
    Realiza chunking automático e gera embeddings vetoriais quando OPENAI_API_KEY disponível.
    Max file size: 10 MB.
    """
    try:
        # 1. Validar extensão
        ext = _get_extension(file.filename)
        if ext not in ALLOWED_EXTENSIONS:
            return {
                "status": "error",
                "message": f"Tipo de arquivo não suportado: '{ext}'. Permitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            }

        # 2. Ler conteúdo e validar tamanho
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            return {
                "status": "error",
                "message": f"Arquivo excede o limite de {MAX_FILE_SIZE // (1024 * 1024)} MB",
            }

        if len(content) == 0:
            return {"status": "error", "message": "Arquivo vazio"}

        # 3. Extrair texto conforme tipo
        extractor = EXTRACTORS[ext]
        raw_text = await asyncio.to_thread(extractor, content)

        if not raw_text or len(raw_text.strip()) < 50:
            return {
                "status": "error",
                "message": "Conteúdo extraído muito curto ou vazio (mínimo 50 caracteres)",
            }

        raw_text = raw_text.strip()
        file_title = title or file.filename or "uploaded_file"

        # 4. Chunking
        chunks = _chunk_text(raw_text)

        # 5. Inserir cada chunk no Brain com embedding
        inserted = 0
        chunk_ids = []

        for i, chunk in enumerate(chunks):
            embedding = await _get_embedding(chunk)
            chunk_title = (
                f"{file_title} (chunk {i+1}/{len(chunks)})"
                if len(chunks) > 1
                else file_title
            )
            row: dict = {
                "raw_content": chunk,
                "source_type": "file_upload",
                "source_title": chunk_title,
                "pipeline_type": persona or "mauro",
                "chunk_metadata": {
                    "filename": file.filename,
                    "file_extension": ext,
                    "file_size_bytes": len(content),
                    "source_agent": source_agent,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
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
                print(f"[brain/ingest-file] falha chunk {i}: {e}")

        return {
            "status": "ok",
            "filename": file.filename,
            "title": file_title,
            "source_type": "file_upload",
            "file_extension": ext,
            "chunks_total": len(chunks),
            "chunks_inserted": inserted,
            "chunk_ids": chunk_ids,
            "text_length": len(raw_text),
            "message": f"'{file_title}' ingerido no Brain — {inserted} chunks com embedding vetorial",
        }

    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": f"Erro inesperado: {str(e)[:200]}"}
