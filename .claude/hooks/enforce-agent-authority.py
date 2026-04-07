import sys, json, os

input_data = json.load(sys.stdin)
command = input_data.get("tool_input", {}).get("command", "")

if "git push" in command:
    active_agent = os.environ.get("AIOS_ACTIVE_AGENT", "")
    if active_agent != "devops":
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"[AIOS] git push bloqueado. "
                f"Agente ativo: '{active_agent}'. "
                f"Apenas @devops (Gage) pode fazer push. "
                f"Ative @devops com: /AIOS:agents:devops"
            )
        }))
        sys.exit(0)

print(json.dumps({"decision": "allow"}))
