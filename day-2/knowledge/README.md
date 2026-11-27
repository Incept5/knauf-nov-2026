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
| `python3 rag.py "question" --show-chunks` | RAG: chunk, embed, retrieve top-k, answer **with sources**, say "not in sources" |
| `python3 rag.py "question" --search-only` | just the retrieval: which chunks are closest to the question |
| `python3 full_context.py "question"` | the opposite: all documents in the prompt (slower, more tokens, sees everything) |
| `python3 compare_retrieval.py` | the 8 questions in `questions.json` through both, with a hit/miss table (16 model calls: 30 s to 2 min on a fast Mac) |
| `python3 compare_retrieval.py --offline-demo` | same table, no network: saved embeddings, **answers are canned** |
| `python3 extract_json.py` | structured extraction + validation + one retry (`--schema` prints the schema) |
| `python3 tool_demo.py` | tool calling: model asks, our code runs a function, result goes back |
| `python3 tool_demo.py --offline-demo` | the same flow with a scripted fake model (`--wire responses` for the other format) |
| `python3 -m unittest test_offline -v` | self-tests, no network |

Options worth trying: `--k 2` / `--k 8` (`rag.py`, `compare_retrieval.py`), `--backend astra`, `--harden` (anti-injection rule),
`--docs your_file.txt`, `compare_retrieval.py --only 1,3 --full-answers` (read the answers, not only the table).
Your own `.txt` or `.md` files work in `--docs` (PDFs do not: extract the text first).

## Embeddings: searching by meaning

An embedding model turns each text into a vector, so texts that mean similar things end up close together. A German question
finds an English paragraph, and "drywall" finds "plasterboard". The Incept5 cluster serves `qwen3-embedding-4b` at
`/v1/embeddings` with the same key as chat, so there is nothing to download.

```bash
python3 rag.py "Wie groß darf der Ständerabstand bei einer Trennwand höchstens sein?"   # German question
python3 rag.py "My drywall arrived broken" --search-only                               # see what is retrieved
```

Things to know:
- **Questions and documents are embedded differently:** Qwen wants an instruction prefix on the question only (see `rag_lib.py`).
- **Send chunks in batches,** not one request each: the server limits requests per second.
- Retrieval always returns something, however irrelevant. The model still has to say "NOT IN SOURCES".
- On your own machine: `--backend local` uses Ollama's `qwen3-embedding:4b` (or set `LLM_EMBED_MODEL`).
- `--backend astra` answers with Astra but still embeds on the cluster, so both keys are needed.
- Real systems often add exact-word search for part numbers and names.

## What to watch for

- **Conflicts.** Two documents give different stud spacings. Does the answer mention both? Does it notice the dates?
- **Outdated documents.** The 2025 delivery SLA is superseded, but nothing in the 2025 file says so. Retrieval cannot know.
- **Split facts.** The 90-minute wall answer lives in several places. With `rag.py ... --k 2` what is lost?
- **No answer.** Question 8 is not in the documents. Does the model say `NOT IN SOURCES` or invent a price?
- **Language.** Question 5 is German and so is its document. Ask it in English too: does it still find the datasheet?
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
- **Embeddings checked live (27 Nov 2026)** on the cluster with the workshop key: the 8 questions retrieved their sources 8 of 8,
  as did 8 harder German or reworded questions. Locally, Ollama's `qwen3-embedding:4b` works too.
- `canned/` is labelled in the output: RAG answers were recorded from a real model, full-context answers written by hand, and
  `embeddings.json` holds saved vectors for these documents and questions only.

## DSGVO articles as JSON (German)

`python3 scrape_gdpr_article-de.py` turns articles of the German GDPR into JSON (`regulation`, `articles` with title, summary and
full text). The code copies the legal text; only the summary comes from the model, so check it. Name article numbers, use `--all`
for all 99, `--backend local` for your own machine. Art. 17 and 22 are saved in `dsgvo/`, so they work without the website.
Text: Regulation (EU) 2016/679, German version, as shown on dsgvo-gesetz.de.
