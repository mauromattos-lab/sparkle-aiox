import sys
import json
import os

input_data = json.load(sys.stdin)
tool_name = input_data.get("tool_name", "")
command = input_data.get("tool_input", {}).get("command", "")

# Só interessa comandos git push (não git commit, git status, etc.)
# Usa word boundary check para evitar false positive em commit messages
command_stripped = command.strip()
is_git_push = (
    command_stripped.startswith("git push") or
    " git push " in command_stripped or
    command_stripped == "git push"
)

if not is_git_push:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

# Verifica agente ativo: env var OU arquivo sentinel
active_agent = os.environ.get("AIOS_ACTIVE_AGENT", "")

# Sentinel file: .claude/.active-agent (persiste no filesystem)
sentinel_path = os.path.join(os.path.dirname(__file__), ".active-agent")
if not active_agent and os.path.exists(sentinel_path):
    with open(sentinel_path, "r") as f:
        active_agent = f.read().strip()

if active_agent != "devops":
    print(json.dumps({
        "decision": "block",
        "reason": f"[AIOS] git push bloqueado. Agente ativo: '{active_agent}'. Apenas @devops (Gage) pode fazer push. Ative @devops com: /AIOS:agents:devops"
    }))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
sys.exit(0)
