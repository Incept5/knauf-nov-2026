# Day 2: Knowledge systems and tool calling

Hands-on code for "Multimodal AI & Knowledge Systems" and "Advanced Context & AI Integration". Python 3, **standard library
only**: nothing to install. All documents in `docs/` are invented (one is German); some contradict each other **on purpose**.

## Setup

```
export INCEPT5_API_KEY=...      # cluster backend (on your handout)   -- or --
export ASTRA_KEY=...            # Astra backend, plus LLM_ASTRA_BASE=... (both on your handout)
cd day-2/knowledge
```
Models are reached through `../common/llm.py` (do not edit it). The default backend is `cluster`; every script takes
`--backend cluster|astra|local`. `local` means a model on your own machine (Ollama with `qwen3.5:9b` by default; do not use
LM Studio with thinking models: they may return nothing). No key and no local model? Use the `--offline-demo` options below
(`compare_retrieval.py` and `tool_demo.py` only).

## What to run

| Script | Demonstrates |
|---|---|
| `python3 bm25_rag.py "question" --show-chunks` | RAG: chunk, index, retrieve top-k, answer **with sources**, say "not in sources" |
| `python3 full_context.py "question"` | the opposite: all documents in the prompt (slower, more tokens, sees everything) |
| `python3 compare_retrieval.py` | the 8 questions in `questions.json` through both, with a hit/miss table (16 model calls: 30 s to 2 min on a fast Mac) |
| `python3 compare_retrieval.py --offline-demo` | same table, no network: retrieval is real, **answers are canned** |
| `python3 extract_json.py` | structured extraction + validation + one retry (`--schema` prints the schema) |
| `python3 tool_demo.py` | tool calling: model asks, our code runs a function, result goes back |
| `python3 tool_demo.py --offline-demo` | the same flow with a scripted fake model (`--wire responses` for the other format) |
| `python3 -m unittest test_offline -v` | self-tests, no network |

Options worth trying: `--k 2` / `--k 8` (`bm25_rag.py`, `compare_retrieval.py`), `--backend astra`, `--harden` (anti-injection rule),
`--docs your_file.txt`, `compare_retrieval.py --only 1,3 --full-answers` (read the answers, not only the table).
Your own `.txt` or `.md` files work in `--docs` (PDFs do not: extract the text first).

## Why BM25 and not embeddings?

Real systems usually use **embeddings**: a model turns text into vectors so that "plasterboard" and "drywall", or an English
question and a German paragraph, land close together. That needs an embedding model, and on locked-down laptops we cannot
download one. **BM25** is a classic keyword ranking that runs anywhere in pure Python and shows the same pipeline:
**chunk, index, retrieve, answer with sources**. Its limits are the point of some exercises: it only matches words that
are actually there (no synonyms, no translation), it knows nothing about meaning, dates or which document is newer, and a
fact split over several chunks may not be retrieved together. Production systems often combine BM25 and embeddings.
`rag_lib.py` also has a plain TF-IDF scorer (`--method tfidf`) and a fuzzy fallback when nothing matches.

## What to watch for

- **Conflicts.** Two documents give different stud spacings. Does the answer mention both? Does it notice the dates?
- **Outdated documents.** The 2025 delivery SLA is superseded, but nothing in the 2025 file says so. Retrieval cannot know.
- **Split facts.** The 90-minute wall answer lives in several places. With `bm25_rag.py ... --k 2` what is lost?
- **No answer.** Question 8 is not in the documents. Does the model say `NOT IN SOURCES` or invent a price?
- **Language.** An English question will not find a German paragraph with BM25 (question 5 is in German for that reason).
- **Prompt injection.** `release_process_note.md` hides an instruction. Compare question 7 with and without `--harden`.
  Current models often ignore it even without the rule. That is not a guarantee.
- **Cost.** Full-context sends about 5,000 tokens for every question; RAG sends about 700. With 8 documents that is fine. With 8,000, it is not possible.
- **Validation.** In `extract_json.py` a reply can be valid JSON and still be wrong. Check values against the source.

## Discussion questions

1. When is full-context better than RAG? When does it stop working (size, cost, speed, "lost in the middle")?
2. How would you keep a knowledge base current? Who owns each document? What happens to superseded versions?
3. Should the assistant resolve conflicts, or show them to a human? How do you show the source and its date?
4. Which tool actions would you allow with no approval, with approval, or never? (see `security_notes.md`)
5. What would you log, and who would read it?
6. For your own documents (Jira tickets, specs, PR history), which approach would you try first and how would you measure it?

## Honest status

- Checked live on local models (25 Nov 2026): the RAG, full-context, comparison, extraction and tool scripts.
- **Cluster checked live (25 Nov 2026)** with `qwen3.6-35b`, `deepseek-v4.1-flash` and `qwen3.8-27b`: all five scripts,
  including tool calling. `compare_retrieval.py` took about 20 s, 40 s and 80 s respectively. To switch model: `export LLM_CLUSTER_MODEL=...`
- **Astra has not been tested live with these scripts**: its request format is tested against a local mock server only.
- Tool calling worked with Ollama (`qwen3.5:9b`, `qwen3.5:4b`), `mlx_lm.server` (Qwen3.8-27B) and LM Studio. If a server
  ignores the `tools` parameter, `tool_demo.py` says so (exit code 3): do not trust the numbers in that answer.
- The `Hit` column only checks which files were cited. A correct answer can show `NO` (it used a different correct
  file) and a poor answer can show `yes`. Token counts are rough (characters / 4).
- If you use Ollama on a laptop and full-context answers look strangely incomplete, its context window may be too small
  for the ~5,000-token prompt: restart it with `OLLAMA_CONTEXT_LENGTH=16384`.
- `canned/` answers are illustrative, written by hand, and are labelled as canned in the output.
