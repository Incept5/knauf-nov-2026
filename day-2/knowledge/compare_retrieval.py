"""Run the 8 questions in questions.json through RAG and through full-context, and print one comparison table.

    python3 compare_retrieval.py [--backend cluster|astra|local] [--k 4] [--harden] [--only 1,3] [--full]
    python3 compare_retrieval.py --offline-demo      # no network: retrieval is real, model answers are CANNED

Columns: Hit = did the answer cite every expected document (for the unanswerable question: did it say NOT IN SOURCES);
Ret = (RAG only) was at least one chunk of each expected document retrieved (file level, not fact level). Hit=no with Ret=yes means the model
had the facts and still failed; Ret=no means retrieval lost them before the model ever saw them.
"""
import argparse
import json
import os

from rag_lib import (DEFAULT_DOCS, HERE, NOT_FOUND, build_chunks, cited_files, estimate_tokens, full_context_prompt,
                     read_docs, run_full, run_rag, system_prompt)
from llm import BACKENDS   # rag_lib puts ../common on the path


def is_hit(q, answer, cited):
    if not q["answerable"]:
        return NOT_FOUND.lower() in answer.lower()
    return all(f in cited for f in q["expected_sources"])


def snippet(text, n=70):
    one = " ".join(text.split())
    return one if len(one) <= n else one[: n - 3] + "..."


def canned_fn(canned, qid):
    entry = canned[str(qid)]
    return lambda prompt: (entry["answer"], entry["seconds"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", default=DEFAULT_DOCS)
    ap.add_argument("--questions", default=os.path.join(HERE, "questions.json"))
    ap.add_argument("--backend", choices=list(BACKENDS), default=None, help="cluster, astra or local (default: LLM_BACKEND or cluster)")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--harden", action="store_true", help="add an anti-prompt-injection rule to the system prompt")
    ap.add_argument("--only", default="", help="comma-separated question ids, e.g. 1,3,7")
    ap.add_argument("--full-answers", action="store_true", help="print complete answers under the table")
    ap.add_argument("--offline-demo", action="store_true", help="use canned model answers from canned/ (no network)")
    a = ap.parse_args()

    questions = json.load(open(a.questions, encoding="utf-8"))
    if a.only:
        wanted = {int(x) for x in a.only.split(",")}
        questions = [q for q in questions if q["id"] in wanted]
    docs = read_docs(a.docs)
    chunks = build_chunks(docs)
    canned = {}
    if a.offline_demo:
        canned = {m: json.load(open(os.path.join(HERE, "canned", m + ".json"), encoding="utf-8")) for m in ("rag", "full")}
        print("*** OFFLINE DEMO: retrieval and token counts are real, but every ANSWER and TIME below is CANNED "
              "(written in advance to illustrate typical behaviour). Run without --offline-demo to use a real model. ***\n")
    print(f"{len(docs)} documents, {len(chunks)} chunks, k={a.k}\n")

    rows, details = [], []
    for q in questions:
        for mode in ("RAG ", "FULL"):
            try:
                if mode == "RAG ":
                    fn = canned_fn(canned["rag"], q["id"]) if a.offline_demo else None
                    r = run_rag(q["question"], chunks, a.k, "bm25", a.backend, a.harden, fn)
                    retrieved = {c["file"] for _, c in r["hits"]}
                    ret = "yes" if all(f in retrieved for f in q["expected_sources"]) else "NO"
                    if not q["answerable"]:
                        ret = "-"
                else:
                    fn = canned_fn(canned["full"], q["id"]) if a.offline_demo else None
                    r = run_full(q["question"], docs, a.backend, a.harden, answer_fn=fn)
                    ret = "-"
                answer = r["answer"]
                cited = cited_files(answer, docs)
                hit = "yes" if is_hit(q, answer, cited) else "NO"
                secs, tokens = f"{r['seconds']:.1f}s", f"{r['tokens']:,}"
            except SystemExit as e:           # missing key, network blocked, over budget: show it, carry on
                answer, cited, hit, ret, secs, tokens = f"ERROR: {e}", [], "ERR", "-", "-", "-"
            short = ", ".join(c.replace(".md", "") for c in cited) or "-"
            rows.append((q["id"], mode.strip(), hit, ret, secs, tokens, short, snippet(answer)))
            details.append((q, mode.strip(), answer))

    head = f"{'Q':>2} {'Mode':<4} {'Hit':<3} {'Ret':<3} {'Time':>6} {'~Tokens':>8}  {'Cited documents':<42} Answer"
    print(head)
    print("-" * len(head) + "-" * 40)
    for r in rows:
        print(f"{r[0]:>2} {r[1]:<4} {r[2]:<3} {r[3]:<3} {r[4]:>6} {r[5]:>8}  {snippet(r[6], 42):<42} {r[7]}")

    for mode in ("RAG", "FULL"):
        sel = [r for r in rows if r[1] == mode and r[2] != "ERR"]
        print(f"\n{mode}: {sum(1 for r in sel if r[2] == 'yes')} of {len(sel)} questions hit the expected source(s).")
    print("Tokens are rough (characters / 4). 'Hit' only checks WHICH documents were cited, not whether the answer is "
          "correct: read the answers, and see the facilitator key.")

    if a.full_answers or a.offline_demo:
        print("\n=== Full answers" + (" (CANNED)" if a.offline_demo else "") + " ===")
        for q, mode, ans in details:
            print(f"\nQ{q['id']} {mode}: {q['question']}\n{ans}")


if __name__ == "__main__":
    main()
