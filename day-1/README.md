# Day 1 exercises (starter material)

Everything here works offline except the model calls. **Never put an API key in a file in this folder.**
Knauf's network (Zscaler) blocks almost every `*.ai` site, so **no exercise uses Together.ai or any other hosted
service**. Three backends are used:

| Backend | What | Key (environment variable) |
|---|---|---|
| `cluster` | Incept5 Spark cluster, `https://inference.incept5.com/v1`, model `qwen3.6-35b` (default) | `INCEPT5_API_KEY`, on your handout |
| `astra` | GPT-6 Astra (`/responses` API), model `gpt-6-astra`. Address REDACTED: set `LLM_ASTRA_BASE` | `ASTRA_KEY`, on your handout |
| `local` | A model on your own laptop (Ollama by default, or LM Studio, or `mlx_lm.server`), model e.g. `qwen3.5:9b` | none |

Default to `cluster`; use `astra` only when you want to compare a frontier model. `local` needs nothing but a local server.
URLs and models are defined once, in the CONFIG block at the top of `common/llm.py`; override them with `LLM_<NAME>_BASE` / `LLM_<NAME>_MODEL` environment variables. Local models: keep **thinking off** (see the repo README).

## Set up (5 minutes, do it before Thursday if you can)
1. `export INCEPT5_API_KEY=...` (and `export ASTRA_KEY=...` and `LLM_ASTRA_BASE=...` if you have them)
2. `cd connectivity && python3 test_connection.py` shows what works and what does not. Standard library only, nothing to install.
3. **opencode:** copy `opencode.json` to your project root (or `~/.config/opencode/`). It defines the cluster and starts on it.
   Switch model inside opencode with `/models`.
4. **Calling a model from your own code:** `from llm import chat`, then `chat("...", backend="cluster")`, `backend="astra"` or `backend="local"`.
   See `common/llm.py`. Ask for JSON with `json_mode=True` (and say "JSON" in your prompt).

If a script is blocked by an email spam filter, the `.txt` copies in `connectivity/` are identical.

| Folder | Exercise |
|---|---|
| `ex1-dashboard/` | Interactive dashboard on a year of Munich weather |
| `ex2-existing-code/` | Understand, test and extend an unfamiliar app (3 hidden bugs) |
| `ex3-add-ai/` | Add summarising / extraction / checking with a model (`cluster` vs `astra`) |
| `ex5-spec/` | Spec-driven development with a template |
