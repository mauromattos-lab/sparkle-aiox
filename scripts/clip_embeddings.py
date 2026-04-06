"""
Script local — Calcula CLIP embeddings das imagens da Zenya e insere no Supabase.

Executar UMA VEZ após upload das imagens para o Supabase Storage.

Pré-requisitos (rodar no terminal):
  pip install open-clip-torch torch Pillow supabase python-dotenv

Uso:
  python scripts/clip_embeddings.py

O script:
  1. Lê todas as imagens com embedding_status='pending' da style_library
  2. Baixa cada imagem da public_url
  3. Calcula embedding CLIP ViT-B/32
  4. Atualiza style_library.embedding e embedding_status='done'

Progresso salvo — pode ser interrompido e retomado.
"""
from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path
from io import BytesIO

# Verificar dependências
try:
    import open_clip
    import torch
    from PIL import Image
    import httpx
    from supabase import create_client
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Dependência faltando: {e}")
    print("\nInstale com:")
    print("  pip install open-clip-torch torch Pillow supabase python-dotenv httpx")
    sys.exit(1)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://gqhdspayjtiijcqklbys.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_KEY:
    print("SUPABASE_KEY não encontrada. Configure .env ou variável de ambiente.")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Carregar modelo CLIP
print("Carregando modelo CLIP ViT-B/32...")
model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
model.eval()
print("Modelo carregado.")


def extract_embedding(image_bytes: bytes) -> list[float]:
    """Extrai embedding CLIP de uma imagem em bytes."""
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(image).unsqueeze(0)
    with torch.no_grad():
        embedding = model.encode_image(tensor)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze().tolist()


def process_batch(batch_size: int = 10):
    """Processa imagens com embedding_status='pending' em lotes."""
    processed = 0
    failed = 0

    while True:
        # Buscar próximo lote pendente
        result = (
            supabase.table("style_library")
            .select("id, public_url, storage_path")
            .eq("embedding_status", "pending")
            .limit(batch_size)
            .execute()
        )

        if not result.data:
            print(f"\nConcluído! {processed} processadas, {failed} falhas.")
            break

        for item in result.data:
            item_id = item["id"]
            url = item.get("public_url") or ""

            if not url:
                print(f"  [{item_id}] Sem URL — pulando")
                supabase.table("style_library").update({
                    "embedding_status": "failed"
                }).eq("id", item_id).execute()
                failed += 1
                continue

            try:
                # Baixar imagem
                response = httpx.get(url, timeout=30, follow_redirects=True)
                response.raise_for_status()

                # Calcular embedding
                embedding = extract_embedding(response.content)

                # Atualizar no Supabase
                # pgvector aceita array como string: '[0.1, 0.2, ...]'
                embedding_str = json.dumps(embedding)
                supabase.table("style_library").update({
                    "embedding": embedding_str,
                    "embedding_status": "done",
                }).eq("id", item_id).execute()

                processed += 1
                print(f"  ✓ [{processed}] {item_id[:8]}... — embedding calculado")

            except Exception as e:
                print(f"  ✗ [{item_id[:8]}...] Erro: {e}")
                supabase.table("style_library").update({
                    "embedding_status": "failed"
                }).eq("id", item_id).execute()
                failed += 1

            time.sleep(0.1)  # rate limiting

        print(f"Lote processado. Total: {processed} ✓ | {failed} ✗")

    return processed, failed


if __name__ == "__main__":
    print(f"\nSupabase: {SUPABASE_URL}")
    print("Iniciando cálculo de embeddings CLIP...\n")

    total_processed, total_failed = process_batch(batch_size=10)
    print(f"\nResumo: {total_processed} embeddings calculados, {total_failed} falhas")
