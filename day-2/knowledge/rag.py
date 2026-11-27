"""RAG in 60 lines: chunk the documents, embed them, retrieve the chunks closest in meaning, answer from ONLY those chunks.

    python3 rag.py "What is the maximum stud spacing?" [--docs docs] [--k 4] [--backend cluster|astra|local] [--show-chunks]
    python3 rag.py "Wie groß darf der Ständerabstand sein?"          # German question, mostly English documents
    python3 rag.py "My drywall arrived broken" --search-only         # just the retrieval, no answer

Needs INCEPT5_API_KEY (the cluster serves the embeddings and the chat model), ASTRA_KEY for --backend astra as well, or a
local server (--backend local, Ollama with qwen3-embedding:4b). Nothing to install.
"""
import argparse

from rag_lib import DEFAULT_DOCS, build_chunks, estimate_tokens, read_docs, retrieve, run_rag
from llm import BACKENDS   # rag_lib puts ../common on the path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question")
    ap.add_argument("--docs", default=DEFAULT_DOCS, help="folder of .txt/.md files, or one file")
    ap.add_argument("--k", type=int, default=4, help="how many chunks to retrieve")
    ap.add_argument("--backend", choices=list(BACKENDS), default=None, help="cluster, astra or local (default: LLM_BACKEND or cluster)")
    ap.add_argument("--search-only", action="store_true", help="show the retrieved chunks and stop (no chat model)")
    ap.add_argument("--max-chars", type=int, default=700, help="chunk size limit")
    ap.add_argument("--show-chunks", action="store_true", help="print the retrieved chunks with their scores")
    ap.add_argument("--harden", action="store_true", help="add an anti-prompt-injection rule to the system prompt")
    a = ap.parse_args()

    docs = read_docs(a.docs)
    chunks = build_chunks(docs, a.max_chars)
    print(f"Indexed {len(docs)} documents as {len(chunks)} chunks.")

    if a.search_only:
        for score, c in retrieve(chunks, a.question, a.k, a.backend):
            print(f"  [{c['id']}]  score {score:.2f}  {' '.join(c['text'].split())[:90]}")
        return

    r = run_rag(a.question, chunks, a.k, a.backend, a.harden)

    if a.show_chunks:
        print("\n--- Retrieved chunks ---")
        for score, c in r["hits"]:
            print(f"\n[{c['id']}]  score {score:.2f}\n{c['text']}")
    print("\n--- Answer ---")
    print(r["answer"])
    print("\n--- Sources the model was given ---")
    for score, c in r["hits"]:
        print(f"  [{c['id']}]  score {score:.2f}")
    print(f"\nTime {r['seconds']:.1f}s | prompt+answer ~{r['tokens']:,} tokens (rough: characters / 4) | "
          f"retrieved {len(r['hits'])} of {len(chunks)} chunks")


if __name__ == "__main__":
    main()
