"""RAG in 60 lines: chunk the documents, index with BM25, retrieve the top chunks, answer from ONLY those chunks.

    python3 bm25_rag.py "What is the maximum stud spacing?" [--docs docs] [--k 4] [--backend cluster|astra|local] [--show-chunks]

Needs INCEPT5_API_KEY (cluster) or ASTRA_KEY (astra), or a local model server (--backend local). Nothing to install.
"""
import argparse

from rag_lib import DEFAULT_DOCS, build_chunks, estimate_tokens, read_docs, run_rag
from llm import BACKENDS   # rag_lib puts ../common on the path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question")
    ap.add_argument("--docs", default=DEFAULT_DOCS, help="folder of .txt/.md files, or one file")
    ap.add_argument("--k", type=int, default=4, help="how many chunks to retrieve")
    ap.add_argument("--backend", choices=list(BACKENDS), default=None, help="cluster, astra or local (default: LLM_BACKEND or cluster)")
    ap.add_argument("--method", choices=["bm25", "tfidf"], default="bm25")
    ap.add_argument("--max-chars", type=int, default=700, help="chunk size limit")
    ap.add_argument("--show-chunks", action="store_true", help="print the retrieved chunks with their scores")
    ap.add_argument("--harden", action="store_true", help="add an anti-prompt-injection rule to the system prompt")
    a = ap.parse_args()

    docs = read_docs(a.docs)
    chunks = build_chunks(docs, a.max_chars)
    print(f"Indexed {len(docs)} documents as {len(chunks)} chunks.")

    r = run_rag(a.question, chunks, a.k, a.method, a.backend, a.harden)

    if a.show_chunks:
        print(f"\n--- Retrieved chunks ({r['method']}) ---")
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
