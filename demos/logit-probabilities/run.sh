#!/bin/sh
# Start the Token Probability Analyzer on http://127.0.0.1:7860 (first time: creates .venv and installs).
#   ./run.sh        Qwen3.8-27B (about 30 GB of memory; converted locally from the official weights)
#   ./run.sh 9b     Qwen3.5-9B  (about 10 GB)
cd "$(dirname "$0")" || exit 1
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || exit 1; }
if [ "$1" = "9b" ]; then
  GGUF_MODEL_PATH="$HOME/.lmstudio/models/unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q8_0.gguf"; export GGUF_MODEL_PATH
fi
exec .venv/bin/python logit_probabilities.py
