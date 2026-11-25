#!/usr/bin/env bash
# One-line check of the Incept5 cluster. Needs INCEPT5_API_KEY in the environment (it is on your handout).
curl -sS https://inference.incept5.com/v1/chat/completions \
  -H "Authorization: Bearer ${INCEPT5_API_KEY:?set INCEPT5_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.6-35b","max_tokens":50,"chat_template_kwargs":{"enable_thinking":false},"messages":[{"role":"user","content":"Hello"}]}'
echo
