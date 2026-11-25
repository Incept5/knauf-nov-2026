# Knauf AI Development & Engineering Workshop: code, data and exercises

Munich, Thursday 26 and Friday 27 November 2026. Incept5.

This repository holds everything you run during the workshop: starter code, data, exercises and connection tests.
**The slides are not in this repository.**

## Layout

| Folder | What |
|---|---|
| `day-1/` | Thursday: connection tests, the four hands-on exercises and the spec-driven exercise |
| `day-2/` | Friday: PR review, knowledge (RAG, extraction, tools) and vision packs |

Start with [`day-1/README.md`](day-1/README.md).

## Before Thursday (5 minutes)

Knauf's network blocks almost every `*.ai` site, so nothing here uses Together.ai or any other hosted service.
Three model backends are used. Their URLs and model names are defined in one place, the CONFIG block at the top of
`day-1/common/llm.py` (copies in `day-2/common/` and `day-1/connectivity/`), and can be overridden with environment variables.

| Backend | What | Key (environment variable) |
|---|---|---|
| `cluster` | Incept5 Spark cluster, `https://inference.incept5.com/v1`, model `qwen3.6-35b` (default) | `INCEPT5_API_KEY`, on your handout |
| `astra` | GPT-6 Astra, model `gpt-6-astra`. Address REDACTED: set `LLM_ASTRA_BASE` | `ASTRA_KEY`, on your handout |
| `local` | A model on your own laptop: Ollama (`http://localhost:11434/v1`, default), LM Studio or `mlx_lm.server` | none |

```bash
git clone git@github.com:Incept5/knauf-nov-2026.git
cd knauf-nov-2026/day-1/connectivity
export INCEPT5_API_KEY=...        # from your handout
python3 test_connection.py        # standard library only, nothing to install; also finds local servers
```

**Choosing the backend:** every script takes `--backend cluster|astra|local`, or set `LLM_BACKEND`. To change a URL or model without
editing code: `LLM_LOCAL_BASE=http://localhost:1234/v1 LLM_LOCAL_MODEL=qwen3.5-9b-mlx@4bit`.

**Local models: switch thinking OFF.** Reasoning models can spend the whole token budget "thinking" and return an empty answer.
`llm.py` asks every backend for no thinking and raises a clear error if a reply is empty because of it. Ollama honours that; LM Studio
does not (use a non-reasoning model there); `mlx_lm.server` needs `--chat-template-args '{"enable_thinking": false}'`.

**Never put an API key in a file or commit one.** Keys are read from environment variables only.

If an email filter blocks the scripts, the `.txt` copies in `day-1/connectivity/` are identical.
