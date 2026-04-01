"""
Onboarding Autônomo — Sprint 8.

Pipeline:
1. Scrapa site do cliente (httpx + extração de texto)
2. Claude Sonnet gera KB (20-30 itens) + system prompt personalizado
3. Cria registro em `clients` (se não existir)
4. Insere KB em `zenya_knowledge_base`
5. Clona workflows Zenya via n8n API (4 workflows core)
6. Notifica Mauro com resumo

Ativação:
- WhatsApp: "onborda [nome] site:[url] tipo:[tipo] telefone:[55...]"
- API: POST /friday/onboard com payload JSON

Modelos:
- Claude Sonnet 4.6 — geração de KB + system prompt (qualidade)
- Claude Haiku — extração de metadados simples
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

# Workflows Zenya Prime a clonar (IDs do master)
ZENYA_MASTER_WORKFLOWS = [
    "G0ormrjMIPrTEnVH",  # 01 — Secretária v3
    "r3C1FMc6NIi6eCGI",  # 05 — Escalar humano
    "ttMFxQ2UsIpW1HKt",  # 07 — Quebrar e enviar
    "4GWd6qHwbJr3qLUP",  # 00 — Configurações
]

N8N_BASE = "https://n8n.sparkleai.tech/api/v1"
N8N_KEY = None  # carregado no runtime via settings (injetado se disponível)


# ── HTML utils ─────────────────────────────────────────────

async def _scrape_site(url: str) -> str:
    """Baixa a página e extrai texto limpo (sem tags HTML). Máx 8.000 chars."""
    if not url:
        return ""
    # Adiciona https:// se não tiver esquema
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        r = await asyncio.to_thread(
            lambda: httpx.get(url, timeout=15, follow_redirects=True, verify=False, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SparkleBot/1.0)"
            })
        )
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"[onboard] scrape falhou ({url}): {e}")
        return ""

    # Remove script/style
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Normaliza espaços
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]


# ── Geração de KB + system prompt ─────────────────────────

_KB_SYSTEM = """Você é um especialista em configurar assistentes virtuais para pequenas empresas brasileiras.

Dado o conteúdo do site e os dados do cliente, gere:
1. Uma lista de 20-30 itens de base de conhecimento (KB) para a Zenya (assistente virtual)
2. Um system prompt completo para a Zenya

FORMATO DE SAÍDA — JSON válido sem markdown:
{
  "kb_items": [
    {"category": "produto", "question": "Qual o preço do X?", "answer": "O X custa R$Y.", "tags": ["produto", "preco"]},
    ...
  ],
  "system_prompt": "Você é [nome], assistente virtual da [empresa]...",
  "business_summary": "Empresa: [nome]. Tipo: [tipo]. O que faz: [resumo 1 linha]."
}

CATEGORIAS válidas para KB: produto, servico, preco, localizacao, horario, pagamento, entrega, faq, contato, sobre_empresa, pedido, garantia

REGRAS para o system_prompt:
- Nome da assistente: Zenya (a menos que o cliente peça outro nome)
- Tom: amigável, profissional, em português brasileiro
- Incluir: fluxo de atendimento, como escalar para humano, regras críticas
- Tamanho: 2.000-4.000 chars
- Não inventar preços ou informações que não estão nos dados fornecidos — use [PENDENTE] para dados faltantes

IMPORTANTE: Responda APENAS com JSON válido, sem blocos de código, sem markdown."""


async def _generate_kb_and_prompt(
    business_name: str,
    business_type: str,
    site_content: str,
    phone: str = "",
    extra_info: str = "",
    task_id: Optional[str] = None,
) -> dict:
    """Chama Claude Sonnet para gerar KB + system prompt."""
    context = f"""
NOME DO NEGÓCIO: {business_name}
TIPO DE NEGÓCIO: {business_type}
TELEFONE: {phone or '[não informado]'}
INFORMAÇÕES EXTRAS: {extra_info or '[nenhuma]'}

CONTEÚDO DO SITE:
{site_content or '[site não disponível ou não informado]'}
""".strip()

    raw = await call_claude(
        prompt=context,
        system=_KB_SYSTEM,
        model="claude-sonnet-4-6",
        client_id=settings.sparkle_internal_client_id,
        task_id=task_id,
        agent_id="friday",
        purpose="onboarding_kb_generation",
        max_tokens=4096,
    )

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = [l for l in cleaned.splitlines() if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[onboard] JSON parse falhou: {e}\nRaw: {raw[:300]}")
        return {"kb_items": [], "system_prompt": "", "business_summary": ""}


# ── Supabase: criar cliente + inserir KB ───────────────────

async def _upsert_client(
    business_name: str,
    business_type: str,
    phone: str,
    client_id: Optional[str] = None,
) -> str:
    """Cria ou atualiza registro em `clients`. Retorna client_id."""
    if not client_id:
        client_id = str(uuid.uuid4())

    slug = re.sub(r"[^a-z0-9]+", "-", business_name.lower()).strip("-")

    try:
        await asyncio.to_thread(
            lambda: supabase.table("clients").upsert({
                "id": client_id,
                "name": business_name,
                "slug": slug,
                "type": business_type,
                "phone": phone,
                "status": "onboarding",
                "mrr": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="id").execute()
        )
        return client_id
    except Exception as e:
        print(f"[onboard] upsert client falhou: {e}")
        return client_id


async def _insert_kb(client_id: str, kb_items: list[dict]) -> int:
    """Insere itens de KB em `zenya_knowledge_base`. Retorna qtd inserida."""
    if not kb_items:
        return 0

    records = []
    for item in kb_items:
        records.append({
            "client_id": client_id,
            "category": item.get("category", "faq"),
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "tags": item.get("tags", []),
            "source": "auto_onboarding",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_knowledge_base").insert(records).execute()
        )
        return len(records)
    except Exception as e:
        print(f"[onboard] insert KB falhou: {e}")
        return 0


# ── n8n: clonar workflows ──────────────────────────────────

def _clone_workflows_n8n(
    business_name: str,
    slug: str,
    phone: str,
    client_id: str,
    system_prompt: str,
) -> list[dict]:
    """
    Clona os 4 workflows Zenya core no n8n.
    Retorna lista de {name, id} dos workflows criados.
    """
    import os
    api_key = os.environ.get("N8N_API_KEY", "")
    if not api_key:
        print("[onboard] N8N_API_KEY ausente — pulando clone de workflows")
        return []

    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    created = []

    workflow_names = {
        "G0ormrjMIPrTEnVH": f"01. {business_name} - Secretária v3",
        "r3C1FMc6NIi6eCGI": f"05. {business_name} - Escalar humano",
        "ttMFxQ2UsIpW1HKt": f"07. {business_name} - Quebrar e enviar mensagens",
        "4GWd6qHwbJr3qLUP": f"00. {business_name} - Configurações",
    }

    for master_id, new_name in workflow_names.items():
        try:
            # Busca workflow master
            r = httpx.get(
                f"{N8N_BASE}/workflows/{master_id}",
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
            wf = r.json()

            # Ajusta nome e limpa metadata
            wf["name"] = new_name
            wf.pop("id", None)
            wf.pop("versionId", None)
            wf.pop("createdAt", None)
            wf.pop("updatedAt", None)
            wf["tags"] = [{"name": "Compartilhado"}]
            wf["active"] = False  # inativo até go-live

            # Injeta system_prompt no nó 00-Configurações
            if "Configurações" in new_name:
                for node in wf.get("nodes", []):
                    if node.get("type") == "n8n-nodes-base.set":
                        params = node.get("parameters", {})
                        assignments = params.get("assignments", {}).get("assignments", [])
                        for a in assignments:
                            if a.get("name") == "system_prompt":
                                a["value"] = system_prompt
                            if a.get("name") == "cliente_telefone":
                                a["value"] = phone
                            if a.get("name") == "cobranca_valor":
                                a["value"] = 0  # será atualizado manualmente

            # Cria cópia no n8n
            res = httpx.post(
                f"{N8N_BASE}/workflows",
                headers=headers,
                json=wf,
                timeout=15,
            )
            res.raise_for_status()
            new_wf = res.json()
            created.append({"name": new_name, "id": new_wf.get("id", "?")})
            print(f"[onboard] workflow criado: {new_name} → {new_wf.get('id')}")

        except Exception as e:
            print(f"[onboard] clone workflow {master_id} falhou: {e}")

    return created


# ── Handler principal ──────────────────────────────────────

async def handle_onboard_client(task: dict) -> dict:
    """
    Onboarding autônomo de novo cliente Zenya.

    Payload esperado:
    {
        "business_name": "Confeitaria Maria",
        "business_type": "confeitaria",
        "site_url": "mariaconfeitaria.com.br",
        "phone": "5511999999999",
        "extra_info": "...",
        "client_id": "<uuid opcional — se já existe no Supabase>"
    }
    """
    payload = task.get("payload", {})
    task_id = task.get("id")

    business_name: str = payload.get("business_name", "").strip()
    business_type: str = payload.get("business_type", "negócio").strip()
    site_url: str = payload.get("site_url", "").strip()
    phone: str = payload.get("phone", "").strip()
    extra_info: str = payload.get("extra_info", "").strip()
    client_id: Optional[str] = payload.get("client_id")

    if not business_name:
        return {"message": "Onboarding falhou — nome do negócio não informado."}

    from_number = payload.get("from_number") or ""
    steps = []

    # 1. Scrape site
    print(f"[onboard] Iniciando onboarding: {business_name} ({site_url})")
    site_content = await _scrape_site(site_url) if site_url else ""
    steps.append(f"Site: {'scraped' if site_content else 'indisponível'}")

    # 2. Gerar KB + system prompt
    generated = await _generate_kb_and_prompt(
        business_name=business_name,
        business_type=business_type,
        site_content=site_content,
        phone=phone,
        extra_info=extra_info,
        task_id=task_id,
    )
    kb_items = generated.get("kb_items", [])
    system_prompt = generated.get("system_prompt", "")
    business_summary = generated.get("business_summary", "")
    steps.append(f"KB: {len(kb_items)} itens gerados")

    # 3. Criar/atualizar cliente no Supabase
    slug = re.sub(r"[^a-z0-9]+", "-", business_name.lower()).strip("-")
    actual_client_id = await _upsert_client(business_name, business_type, phone, client_id)
    steps.append(f"Cliente: {actual_client_id[:8]}...")

    # 4. Inserir KB
    kb_count = await _insert_kb(actual_client_id, kb_items)
    steps.append(f"KB inserida: {kb_count} registros")

    # 5. Clonar workflows n8n
    workflows = await asyncio.to_thread(
        _clone_workflows_n8n,
        business_name=business_name,
        slug=slug,
        phone=phone,
        client_id=actual_client_id,
        system_prompt=system_prompt,
    )
    steps.append(f"Workflows: {len(workflows)}/4 clonados")

    # 6. Salvar system_prompt como nota no Supabase
    try:
        await asyncio.to_thread(
            lambda: supabase.table("notes").insert({
                "client_id": actual_client_id,
                "agent_id": "friday",
                "task_id": task_id,
                "content": system_prompt,
                "summary": f"System prompt gerado para {business_name}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        )
    except Exception as e:
        print(f"[onboard] save system_prompt falhou: {e}")

    # 7. Montar mensagem resumo para Mauro
    wf_lines = "\n".join(f"  • {w['name']} (ID: {w['id']})" for w in workflows) or "  • nenhum (sem N8N_API_KEY)"
    pending = []
    if not phone:
        pending.append("• Adicionar número WhatsApp do cliente")
    if not site_url or not site_content:
        pending.append("• Verificar/completar KB (site indisponível)")
    if not workflows:
        pending.append("• Clonar workflows manualmente (sem N8N_API_KEY)")
    pending.append("• Criar instância Z-API para o cliente")
    pending.append("• Ativar workflows após QA")
    pending.append("• Configurar id_conversa_alerta no node Info")

    pending_str = "\n".join(pending)

    summary = (
        f"✅ Onboarding iniciado: *{business_name}*\n\n"
        f"{business_summary}\n\n"
        f"📋 Executado:\n" +
        "\n".join(f"  • {s}" for s in steps) +
        f"\n\n🔧 Workflows criados:\n{wf_lines}\n\n"
        f"⏳ Pendente (ação manual):\n{pending_str}"
    )

    return {"message": summary, "client_id": actual_client_id, "kb_count": kb_count}
