#!/usr/bin/env python3
"""Run the AI review and the risk gate over every pull request in prs/ and print a summary table.

    python3 run_all.py                    review every PR with the model (needs a key and a network)
    python3 run_all.py --offline-demo     use the CANNED answers in canned/ (no network, no key)
    python3 run_all.py --only 03          just the PRs whose name contains "03"
    python3 run_all.py -v                 also print the gate's reasons for each PR
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review as rv                                   # noqa: E402
from risk_gate import decide                          # noqa: E402


def load_canned(name):
    """Canned answers go through the same parse + validate steps as real model replies."""
    raw = (HERE / "canned" / f"{name}.json").read_text()
    clean, _ = rv.validate_review(rv.parse_model_json(raw))
    return clean


def main(argv=None):
    ap = argparse.ArgumentParser(description="Review + gate every PR in prs/.")
    ap.add_argument("--offline-demo", action="store_true", help="use canned answers instead of calling a model")
    ap.add_argument("--backend", choices=list(rv.llm.BACKENDS))
    ap.add_argument("--standards", default=str(rv.DEFAULT_STANDARDS))
    ap.add_argument("--context", metavar="DIR", help="send changed files from DIR as extra context")
    ap.add_argument("--only", default="", help="only PRs whose file name contains this text")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the gate's reasons")
    args = ap.parse_args(argv)

    diffs = sorted(p for p in (HERE / "prs").glob("*.diff") if args.only in p.name)
    if not diffs:
        print("No matching PRs found in prs/", file=sys.stderr)
        return 2
    standards = Path(args.standards).read_text()

    if args.offline_demo:
        print("*** OFFLINE DEMO: the model answers below are CANNED EXAMPLES written by the workshop team,")
        print("*** not real model output. The gate is real: it runs for real on every PR.\n")

    rows, failures = [], 0
    for diff in diffs:
        name = diff.stem
        diff_text = diff.read_text()
        started = time.time()
        error = ""
        try:
            if args.offline_demo:
                review = load_canned(name)
            else:
                description_file = diff.with_suffix(".md")
                description = description_file.read_text().strip() if description_file.is_file() else ""
                review = rv.review_diff(diff_text, standards, args.backend, description, args.context)["review"]
        except (rv.ReviewError, OSError) as exc:
            review, error = None, str(exc)
            failures += 1
        seconds = "canned" if args.offline_demo else f"{time.time() - started:.1f}s"
        decision, reasons = decide(review, diff_text)
        rows.append((name, review["risk"] if review else "n/a", review["recommendation"] if review else "n/a",
                     decision, seconds, reasons, error))

    width = max(len(r[0]) for r in rows)
    print(f"{'PR'.ljust(width)}  {'model risk':<10}  {'model says':<18}  {'gate decision':<20}  time")
    print("-" * (width + 62))
    for name, risk, says, decision, seconds, _, _ in rows:
        print(f"{name.ljust(width)}  {risk:<10}  {says:<18}  {decision:<20}  {seconds}")
    print("\nWhere 'model says' and 'gate decision' differ, the rules overrode the AI. That is the design.")

    if args.verbose or failures:
        for name, _, _, decision, _, reasons, error in rows:
            if args.verbose or error:
                print(f"\n{name}: {decision}")
                if error:
                    print(f"  review failed: {error}")
                for reason in reasons:
                    print(f"  - {reason}")
    if failures == len(rows):
        print("\nEvery review failed. No network or key? Try:  python3 run_all.py --offline-demo", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
