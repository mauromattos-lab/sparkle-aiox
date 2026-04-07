import sys, json, os

input_data = json.load(sys.stdin)
file_path = input_data.get("tool_input", {}).get("file_path", "")

runtime_paths = ["sparkle-runtime/runtime/", "sparkle-runtime/migrations/"]
is_runtime = any(p in file_path for p in runtime_paths)

if not is_runtime:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

current_story = os.environ.get("AIOS_CURRENT_STORY", "")
if not current_story:
    print(json.dumps({
        "decision": "warn",
        "message": (
            "[AIOS] Escrita em runtime sem story ativa. "
            "Se for hotfix, continue. "
            "Se for feature, declare: export AIOS_CURRENT_STORY=CONTENT-2.X"
        )
    }))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
