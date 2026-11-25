#!/usr/bin/env python3
"""The safeguard layer: AI advises, plain rules decide. No model is called here.

    python3 risk_gate.py prs/03-money-rounding.diff review.json

Decisions, from loosest to strictest:  auto_merge_candidate < human_review < block
Rules can only move the decision UP. The model's own recommendation is one more input that can only
make the result stricter, never looser. Exit code: 0 auto_merge_candidate, 1 human_review, 2 block.

Change the numbers and patterns below to match your team's policy.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from diffutil import added_lines, is_doc_file, is_test_file, split_by_file, total_changed  # noqa: E402

MAX_AUTO_MERGE_LINES = 150                                   # added + removed lines
SENSITIVE_PATH = re.compile(r"payment|pricing|auth", re.I)   # money and access: a human always looks

# Crude pattern checks on ADDED lines. They catch the obvious cases even if the model misses them.
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{6,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\w*(?:key|secret|password|passwd|token)\w*\s*=\s*[\"'][^\"']{8,}[\"']", re.I),
]
SQL_CONCAT_PATTERNS = [
    re.compile(r"\b(?:select|insert|update|delete)\b[^\n]*[\"']\s*[+%]\s*\w", re.I),     # "SELECT ... " + value
    re.compile(r"\bf[\"'][^\n]*\b(?:select|insert|update|delete)\b[^\n]*\{", re.I),      # f"SELECT ... {value}"
]

ORDER = ["auto_merge_candidate", "human_review", "block"]


def decide(review, diff_text):
    """Return (decision, reasons). `review` is the model's validated JSON as a dict, or None if it was unusable."""
    decision = "auto_merge_candidate"
    reasons = []

    def raise_to(level, why):
        nonlocal decision
        if ORDER.index(level) > ORDER.index(decision):
            decision = level
        reasons.append(f"[{level}] {why}")

    files = [path for path, _ in split_by_file(diff_text)]
    code_files = [p for p in files if not is_doc_file(p) and not is_test_file(p)]
    added = added_lines(diff_text)

    # 1. Rules that read only the diff (they still work if the model says nothing useful)
    if not files:
        raise_to("human_review", "the diff is empty or could not be read")
    if any(pattern.search(line) for line in added for pattern in SECRET_PATTERNS):
        raise_to("block", "an added line looks like a hard-coded secret")
    if any(pattern.search(line) for line in added for pattern in SQL_CONCAT_PATTERNS):
        raise_to("block", "an added line looks like SQL built from strings")
    sensitive = [p for p in code_files if SENSITIVE_PATH.search(p)]
    if sensitive:
        raise_to("human_review", "touches a payment/pricing/auth path: " + ", ".join(sensitive))
    size = total_changed(diff_text)
    if size > MAX_AUTO_MERGE_LINES:
        raise_to("human_review", f"{size} changed lines is more than {MAX_AUTO_MERGE_LINES}")
    if code_files and not any(is_test_file(p) for p in files):
        raise_to("human_review", "code changed but no test file changed")

    # 2. Rules about the model's answer
    if review is None:
        raise_to("human_review", "the model's answer could not be parsed, so there is no review to trust")
    else:
        if review.get("incomplete"):
            raise_to("human_review", "part of the diff could not be reviewed by the model")
        if any(f.get("category") == "security" for f in review.get("findings", [])):
            raise_to("block", "the model reported a security finding")
        if review.get("recommendation") == "block":
            raise_to("block", "the model recommends blocking")
        elif review.get("recommendation") != "approve":
            raise_to("human_review", f"the model recommends {review.get('recommendation')!r}")
        if review.get("risk") != "low":
            raise_to("human_review", f"the model rates the risk {review.get('risk')!r}")
        serious = [f for f in review.get("findings", []) if f.get("severity") in ("medium", "high")]
        if serious:
            raise_to("human_review", f"the model reported {len(serious)} medium/high finding(s)")

    if decision == "auto_merge_candidate":
        reasons.append("no rule fired and the model agrees: safe to auto-merge once required CI checks pass")
    return decision, reasons


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic merge gate for an AI-reviewed pull request.")
    ap.add_argument("diff")
    ap.add_argument("review_json", help="file written by `review.py --save`")
    ap.add_argument("--json", action="store_true", help="print the decision as JSON")
    args = ap.parse_args(argv)

    diff_text = Path(args.diff).read_text()
    review = None                                   # a missing or broken review file is treated as "no review"
    try:
        loaded = json.loads(Path(args.review_json).read_text())
        review = loaded if isinstance(loaded, dict) else None
    except (OSError, ValueError):
        pass
    decision, reasons = decide(review, diff_text)
    if args.json:
        print(json.dumps({"decision": decision, "reasons": reasons}))
    else:
        print(f"GATE DECISION: {decision}")
        for reason in reasons:
            print(f"  - {reason}")
    return ORDER.index(decision)


if __name__ == "__main__":
    sys.exit(main())
