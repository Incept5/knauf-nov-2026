"""Connection test for the workshop. Run:  python3 test_connection.py
Shows the settings of every backend (cluster, astra, local), asks each one that is set up a tiny question, and looks for
local model servers on this machine. No key is ever printed. The settings live in the CONFIG block at the top of llm.py."""
import json
import sys
import urllib.request

import llm

print("Backends (change them in llm.py, or with LLM_<NAME>_BASE / LLM_<NAME>_MODEL environment variables):\n")
ok = llm.check()

print("\nLocal model servers found on this machine:")
found = False
for label, base, hint in (("Ollama", "http://localhost:11434/v1", "thinking switch works"),
                          ("LM Studio", "http://localhost:1234/v1", "cannot switch thinking off from the API: use non-reasoning models"),
                          ("mlx_lm.server", "http://localhost:8080/v1", "start it with --chat-template-args '{\"enable_thinking\": false}'")):
    try:
        with urllib.request.urlopen(base + "/models", timeout=2) as r:
            names = [m["id"] for m in json.load(r)["data"]]
    except Exception:
        continue
    found = True
    print(f"  {label:14} {base}   {len(names)} models, e.g. {', '.join(names[:3])}\n  {'':14} ({hint})")
if not found:
    print("  none (that is fine: use the cluster or Astra). To use a local model, start Ollama or LM Studio, then set\n"
          "  LLM_LOCAL_BASE and LLM_LOCAL_MODEL (see llm.py).")
sys.exit(0 if ok else 1)
