import sys, json, re

input_data = json.load(sys.stdin)
file_path = input_data.get("tool_input", {}).get("file_path", "")
new_content = input_data.get("tool_input", {}).get("content", "") or \
              input_data.get("tool_input", {}).get("new_string", "")

if "docs/stories" not in file_path:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

if "status: Done" not in new_content and "status: 'Done'" not in new_content:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

has_qa_pass = bool(re.search(r"## QA Results.*?\*\*Resultado:\*\* PASS", new_content, re.DOTALL))

if not has_qa_pass:
    print(json.dumps({
        "decision": "block",
        "reason": (
            "[AIOS] Status 'Done' bloqueado. "
            "Story não tem 'QA Results' com '**Resultado:** PASS'. "
            "Ative @qa para revisar: /AIOS:agents:qa"
        )
    }))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
