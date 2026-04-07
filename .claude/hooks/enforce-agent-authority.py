import sys
import json
import os
import re

input_data = json.load(sys.stdin)
command = input_data.get("tool_input", {}).get("command", "")

# Detecta git push como comando real (não texto dentro de commit message ou compound cmd)
# Divide por separadores de shell e verifica cada subcomando individualmente
def is_real_git_push(cmd):
    parts = re.split(r"&&|\|\||;", cmd)
    for part in parts:
        tokens = part.strip().split()
        # git push deve ser os dois primeiros tokens do subcomando
        if len(tokens) >= 2 and tokens[0] == "git" and tokens[1] == "push":
            return True
    return False

if not is_real_git_push(command):
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

# Verifica agente ativo via sentinel file (env var inline nao propaga ao hook subprocess)
sentinel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".active-agent")
active_agent = ""
if os.path.exists(sentinel_path):
    with open(sentinel_path, "r") as f:
        active_agent = f.read().strip()

# Fallback: env var (funciona se setada no processo pai do Claude Code)
if not active_agent:
    active_agent = os.environ.get("AIOS_ACTIVE_AGENT", "")

if active_agent != "devops":
    print(json.dumps({
        "decision": "block",
        "reason": f"[AIOS] git push bloqueado. Agente ativo: '{active_agent}'. Apenas @devops (Gage) pode fazer push. Ative @devops com: /AIOS:agents:devops"
    }))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
sys.exit(0)
