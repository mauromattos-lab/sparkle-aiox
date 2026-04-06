---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.10
title: "IP Auditor — Validação de Lore via Brain (sparkle-lore)"
status: TODO
priority: P1
executor: "@dev"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.6]
unblocks: [CONTENT-1.11]
estimated_effort: 3-4h de agente (@dev)
---

# Story 1.10 — IP Auditor — Validação de Lore via Brain

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 11 de 13
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR9
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como pipeline de conteúdo,
> quero que um IP Auditor valide cada peça contra o lore da Zenya (namespace `sparkle-lore` no Brain) antes de ir para aprovação,
> para que nenhum conteúdo contradiga a personagem estabelecida ou repita algo publicado recentemente.

---

## Contexto Técnico

**Estado atual:** Brain namespace `sparkle-lore` existe com ~50 chunks de lore básico. O pipeline não consulta o Brain antes de publicar.

**Estado alvo:** `ip_auditor.py` roda entre `assembly_done` e `pending_approval`: consulta sparkle-lore, verifica contradições de lore e similaridade com conteúdo recente. Se flagrar problema, status fica em `pending_approval` mas com flag de alerta para Mauro revisar com atenção.

**Nota importante:** IP Auditor **não bloqueia** o pipeline autonomamente — ele sinaliza. A decisão final é sempre de Mauro na aprovação.

---

## Acceptance Criteria

- [ ] **AC1** — `ip_auditor.py` recebe `content_piece` (caption + voice_script + theme) e consulta Brain namespace `sparkle-lore` com a descrição do conteúdo
- [ ] **AC2** — Validação de lore: se Brain retornar chunks de lore que contradizem o conteúdo, IP Auditor registra alerta em `content_pieces.pipeline_log`
- [ ] **AC3** — Validação de repetição: query no Supabase por `content_pieces` com `status = 'published'` nos últimos 7 dias — se tema/caption for muito similar (fuzzy match > 80%), registra alerta de repetição
- [ ] **AC4** — Peça **sempre avança** para `pending_approval` independente de alertas — auditor nunca bloqueia automaticamente
- [ ] **AC5** — Alertas do IP Auditor são salvos em `pipeline_log` com campo `ip_audit: {lore_ok: bool, repetition_ok: bool, warnings: [...]}`
- [ ] **AC6** — Conteúdo publicado é ingerido no Brain namespace `sparkle-lore` após publicação: `{tema, data, caption_resumo, performance_url}` (chamado pelo Publisher — Story 1.11)
- [ ] **AC7** — Image Prompt Engineer (Story 1.2) consulta `sparkle-lore` para restrições de personagem antes de gerar prompt (adicionar chamada ao Brain no início do pipeline)

---

## Dev Notes

### Consulta ao Brain
```python
async def audit_lore(piece: dict) -> dict:
    # Consulta sparkle-lore com descrição do conteúdo
    query = f"{piece['theme']} {piece.get('voice_script', '')[:200]}"
    brain_results = await brain_client.query(
        namespace="sparkle-lore",
        query=query,
        top_k=5
    )
    
    warnings = []
    
    # Verificação simples: se Brain retornar chunks de "proibições"
    # (lore chunks com tag "restriction"), sinalizar
    restrictions = [r for r in brain_results if "restriction" in r.get("tags", [])]
    lore_ok = len(restrictions) == 0
    if not lore_ok:
        warnings.append(f"Possível conflito de lore: {restrictions[0]['content'][:100]}")
    
    # Verificação de repetição
    repetition_ok, repetition_warning = await check_repetition(piece)
    if not repetition_ok:
        warnings.append(repetition_warning)
    
    return {
        "lore_ok": lore_ok,
        "repetition_ok": repetition_ok,
        "warnings": warnings
    }
```

### Verificação de repetição
```python
async def check_repetition(piece: dict) -> tuple[bool, str]:
    recent = supabase.table("content_pieces") \
        .select("theme, caption") \
        .eq("status", "published") \
        .gte("published_at", (now() - timedelta(days=7)).isoformat()) \
        .execute()
    
    for recent_piece in recent.data:
        similarity = fuzz.ratio(piece.get("theme", ""), recent_piece.get("theme", ""))
        if similarity > 80:
            return False, f"Tema muito similar a conteúdo publicado recentemente ({similarity}% match)"
    
    return True, ""
```

### Como adicionar restrições ao sparkle-lore
Após curadoria, ingerir chunks com estrutura:
```json
{
  "content": "A Zenya nunca fala sobre política ou religião",
  "tags": ["restriction", "behavior"],
  "namespace": "sparkle-lore"
}
```

---

## Integration Verifications

- [ ] `ip_auditor.py` consulta Brain `sparkle-lore` sem erro
- [ ] Peça com tema repetido (< 7 dias) gera alerta de repetição no `pipeline_log`
- [ ] Peça com lore conflict gera alerta de lore no `pipeline_log`
- [ ] Peça **sempre** avança para `pending_approval` mesmo com alertas
- [ ] `pipeline_log` contém campo `ip_audit` com estrutura correta após auditoria
- [ ] Image Prompt Engineer consulta sparkle-lore para restrições antes de gerar prompt

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/ip_auditor.py` | Criar | IP Auditor: lore check + repetition check via Brain |
| `runtime/content/image_engineer.py` | Atualizar | Adicionar consulta sparkle-lore no início (restrições de personagem) |
| `tests/test_ip_auditor.py` | Criar | Testes: lore conflict, repetition detection, always-advance behavior |
