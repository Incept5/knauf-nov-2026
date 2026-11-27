"""Structured extraction: turn a free-text document into JSON, then CHECK the JSON with plain Python.

    python3 extract_json.py                          # the two sample documents in extract_docs/
    python3 extract_json.py path/to/file.txt [more files] [--backend cluster|astra|local]
    python3 extract_json.py --schema                 # print the schema and exit

The lesson: a model's JSON is a claim, not a fact. Validate types, required keys and allowed values, and if the check
fails, give the model the exact error and let it try once more. Never trust it silently.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from llm import chat, BACKENDS  # noqa: E402

DEFAULT_FILES = [os.path.join(HERE, "extract_docs", n)
                 for n in ("delivery_note.txt", "site_incident_report.txt")]

# The schema: field -> what it must look like. "null_ok" means the value may be null when the document does not say.
SCHEMA = {
    "date":     {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "null_ok": False,
                 "help": "date of the document as YYYY-MM-DD"},
    "site":     {"type": "string", "null_ok": False, "help": "site or project name"},
    "material": {"type": "string", "null_ok": True, "help": "main material involved, or null"},
    "quantity": {"type": "number", "null_ok": True, "help": "number of items delivered/affected, or null if not stated"},
    "problem":  {"type": "string", "null_ok": False, "help": "one sentence: what went wrong"},
    "owner":    {"type": "string", "null_ok": True, "help": "who must act next, or null"},
    "risk":     {"type": "string", "allowed": ["low", "medium", "high"], "null_ok": False,
                 "help": "your assessment: low, medium or high"},
}


def schema_text():
    lines = ["Return one JSON object with exactly these keys:"]
    for name, spec in SCHEMA.items():
        extra = f" (one of {spec['allowed']})" if "allowed" in spec else ""
        nul = " or null" if spec["null_ok"] else ""
        lines.append(f'  "{name}": {spec["type"]}{nul}{extra}: {spec["help"]}')
    return "\n".join(lines)


def validate(obj, schema=SCHEMA):
    """Return a list of problems (empty list = valid). Plain Python, no libraries."""
    if not isinstance(obj, dict):
        return [f"top level must be a JSON object, got {type(obj).__name__}"]
    errors = []
    for key, spec in schema.items():
        if key not in obj:
            errors.append(f"missing required key '{key}'")
            continue
        v = obj[key]
        if v is None:
            if not spec["null_ok"]:
                errors.append(f"'{key}' must not be null")
            continue
        if spec["type"] == "string":
            if not isinstance(v, str) or not v.strip():
                errors.append(f"'{key}' must be a non-empty string")
                continue
            if "pattern" in spec and not re.match(spec["pattern"], v):
                errors.append(f"'{key}' = {v!r} does not match format {spec['pattern']}")
        elif spec["type"] == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                errors.append(f"'{key}' must be a number, got {type(v).__name__} {v!r}")
        if "allowed" in spec and v not in spec["allowed"]:
            errors.append(f"'{key}' = {v!r} is not one of {spec['allowed']}")
    for key in obj:
        if key not in schema:
            errors.append(f"unexpected key '{key}'")
    return errors


def parse_json(text):
    """Models sometimes wrap JSON in ```fences``` or add a sentence. Take the part from the first { to the last }."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object found in the reply")
    return json.loads(text[start:end + 1])


def extract(document, backend=None, max_tokens=1500):
    """Return (obj_or_None, errors, attempts, last_reply). One retry with the validation error fed back."""
    system = "You extract structured data from documents. Reply with JSON only, no explanation."
    prompt = (f"Extract the fields below from the document and answer in JSON.\n{schema_text()}\n"
              f"Use null when the document does not say. Do not invent facts.\n\nDOCUMENT:\n{document}")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    errors, reply = [], ""
    for attempt in (1, 2):
        reply = chat(prompt, backend=backend, json_mode=True, max_tokens=max_tokens, temperature=0, messages=messages)
        try:
            obj = parse_json(reply)
            errors = validate(obj)
        except ValueError as e:                      # json.JSONDecodeError is a ValueError
            obj, errors = None, [f"reply is not valid JSON: {e}"]
        if not errors:
            return obj, [], attempt, reply
        if attempt == 1:                             # feed the exact problems back, once
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "Your JSON failed validation:\n- " + "\n- ".join(errors) +
                          "\nReturn the corrected JSON object only."}]
    return None, errors, 2, reply


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="text files to read (default: the delivery note and the incident report in extract_docs/)")
    ap.add_argument("--backend", choices=list(BACKENDS), default=None, help="cluster, astra or local (default: LLM_BACKEND or cluster)")
    ap.add_argument("--schema", action="store_true", help="print the schema and exit")
    a = ap.parse_args()
    if a.schema:
        print(schema_text())
        print("\nRules checked by validate(): all keys present, no extra keys, types, date format, allowed risk values.")
        return
    files = a.files or DEFAULT_FILES
    passed = 0
    for f in files:
        print(f"\n=== {os.path.basename(f)}")
        try:
            document = open(f, encoding="utf-8").read()
        except OSError as e:
            print(f"  cannot read: {e}")
            continue
        try:
            obj, errors, attempts, reply = extract(document, a.backend)
        except SystemExit as e:                      # llm.py: no key, no server, or the model returned nothing
            print(f"RESULT: FAIL. {e}")
            continue
        if obj is not None:
            passed += 1
            print(json.dumps(obj, indent=2, ensure_ascii=False))
            print(f"RESULT: PASS (attempt {attempts} of 2)")
        else:
            print("last reply:", reply[:300])
            print("RESULT: FAIL after 2 attempts. Problems:\n  - " + "\n  - ".join(errors))
    print(f"\nSummary: {passed} of {len(files)} documents passed validation.")
    print("Passing validation means the SHAPE is right, not that the values are true. Check them against the document.")


if __name__ == "__main__":
    main()
