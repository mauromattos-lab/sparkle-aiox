"""
Echo handler — test task that returns its own payload.
Used to validate the end-to-end task pipeline.
"""


def handle_echo(task: dict) -> dict:
    payload = task.get("payload", {})
    return {
        "message": f"Echo: {payload.get('original_text', payload)}",
        "received_payload": payload,
    }
