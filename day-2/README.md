# Day 2 (Friday): knowledge, tools and pull-request review

| Folder | What |
|---|---|
| `pr-review/` | AI-assisted pull-request review: six pull requests, a reviewer and a rule-based merge gate |
| `knowledge/` | Retrieval (RAG with embeddings), full context, structured extraction (including GDPR/DSGVO articles as JSON) and tool calling |
| `examples/` | The short scripts shown on the slides: extraction, JSON output, RAG over *Alice in Wonderland* |
| `measurements/` | How the numbers on some slides were produced (presenter, Apple Silicon) |
| `vision/` | Ask a vision model about a rendered page of a German economic report |
| `common/llm.py` | The shared helper: URLs and models are in the CONFIG block at the top |

**Models:** use the cluster (`INCEPT5_API_KEY`). To compare, `--backend astra` (`ASTRA_KEY`). Only if you already run Ollama:
`--backend local` with `qwen3.5:9b` (not LM Studio, not the 4B). Test with `python3 common/test_connection.py`.

**Page images for `vision/`:** `data/pages/muenchen-p12.png`, `-p15.png`, `-p16.png` are in the repository (`git pull` if you
cloned earlier). They are pages of the City of Munich's report and its copyright; see `data/SOURCES.md`.

Every pack works without a network in at least part: `pr-review/run_all.py --offline-demo`, `knowledge/compare_retrieval.py --offline-demo`
and `knowledge/tool_demo.py --offline-demo` use canned answers, clearly labelled.
