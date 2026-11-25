# Exercise 3: add AI to an application (20 min)

Add one of these to your Exercise 1 or 2 app, calling a model with `from llm import chat` (copy `../common/llm.py` next to your
code; see `../README.md` for the three backends: `cluster`, `astra` and `local`):

- **Summarise** a document in `docs/` in three bullet points and a one-line risk rating.
- **Extract** fields as JSON from a document: date, site, material, quantity, problem, who must act.
- **Decide**: "Is this delivery note consistent with the order?" (`docs/delivery_note.txt` and the orders in Exercise 2).

Rules: ask for structured JSON and validate it; run **at least two backends** (`backend="cluster"`, `"astra"` or `"local"`) and compare; note any answer that was
confidently wrong. All documents are invented for this workshop.
