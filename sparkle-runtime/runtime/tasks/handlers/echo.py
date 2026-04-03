"""
Echo handler — test task that returns its own payload.
Used to validate the end-to-end task pipeline.

Flags de teste suportados no payload:
- return_handoff: true  → retorna handoff_to="brain_ingest" para testar Handoff Engine
- brain_worthy: true    → retorna brain_worthy=True para testar Auto-Brain-Ingest
"""


async def handle_echo(task: dict) -> dict:
    payload = task.get("payload", {})
    result: dict = {
        "message": f"Echo: {payload.get('content', payload.get('original_text', str(payload)))}",
        "received_payload": payload,
    }

    # Suporte a testes de handoff engine
    if payload.get("return_handoff"):
        result["handoff_to"] = "brain_ingest"
        result["handoff_payload"] = {
            "content": f"Teste de handoff automático: {payload.get('content', 'echo test')}",
            "source_title": "echo_handoff_test",
            "ingest_type": "test",
        }

    # Suporte a testes de auto-brain-ingest
    if payload.get("brain_worthy"):
        result["brain_worthy"] = True
        result["brain_content"] = f"Conteúdo brain-worthy do echo: {payload.get('content', 'echo test')}"

    return result
