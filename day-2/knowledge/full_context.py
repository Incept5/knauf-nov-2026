"""The opposite of RAG: put EVERY document into the prompt and ask the same question.

    python3 full_context.py "What is the maximum stud spacing?" [--docs docs] [--backend cluster|astra|local] [--budget 120000]

Compare the answer, the time and the token estimate with bm25_rag.py.
"""
import argparse

from rag_lib import DEFAULT_DOCS, cited_files, read_docs, run_full
from llm import BACKENDS   # rag_lib puts ../common on the path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question")
    ap.add_argument("--docs", default=DEFAULT_DOCS)
    ap.add_argument("--backend", choices=list(BACKENDS), default=None, help="cluster, astra or local (default: LLM_BACKEND or cluster)")
    ap.add_argument("--budget", type=int, default=120000, help="refuse if the prompt is longer than this many characters")
    ap.add_argument("--harden", action="store_true", help="add an anti-prompt-injection rule to the system prompt")
    a = ap.parse_args()

    docs = read_docs(a.docs)
    r = run_full(a.question, docs, a.backend, a.harden, a.budget)
    print("--- Answer ---")
    print(r["answer"])
    print("\n--- Documents mentioned in the answer ---")
    print("  " + (", ".join(cited_files(r["answer"], docs)) or "(none)"))
    print(f"\nTime {r['seconds']:.1f}s | prompt+answer ~{r['tokens']:,} tokens (rough: characters / 4) | "
          f"{len(docs)} documents, {len(r['prompt']):,} characters sent")


if __name__ == "__main__":
    main()
