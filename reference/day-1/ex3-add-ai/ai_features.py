"""Exercise 3 reference: summarise / extract / check a document with a model, with JSON validation and ONE retry.
    python3 ai_features.py --task summarise --doc site_incident_report.txt --backend local
    python3 ai_features.py --task extract   --doc delivery_note.txt        --backend cluster
    python3 ai_features.py --task check     --doc delivery_note.txt        --backend astra
All model settings are in llm.py (copy day-1/common/llm.py next to this file, or it is found automatically). Standard library only."""
import argparse, json, pathlib, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2] / "day-1"
for p in (HERE, REPO / "common"):
    if (p / "llm.py").exists():
        sys.path.insert(0, str(p)); break
import llm
from llm import chat

DOCS = next(p for p in (HERE / "docs", REPO / "ex3-add-ai/docs") if p.exists())
DATA = next(p for p in (HERE / "data", REPO / "ex2-existing-code/order_pricing/data") if p.exists())

SYSTEM = ("You process building-industry documents. Reply with ONE JSON object only: no markdown, no commentary. "
          "Use only facts in the document. If something is not stated, use null. Never guess.")

PROMPTS = {
    "summarise": 'Summarise the document. JSON shape: {"bullets": [three short strings], "risk": "low"|"medium"|"high", "risk_reason": "one line"}\n'
                 "Rate the risk for the site or the project.\n\nDOCUMENT:\n{doc}",
    "extract": 'Extract these fields. JSON shape: {"date": "YYYY-MM-DD", "site": string|null, "material": string|null, '
               '"quantity": number|null, "unit": string|null, "problem": string|null, "who_must_act": [strings, empty if none]}\n\nDOCUMENT:\n{doc}',
    "check": "Is this delivery note consistent with the order? 'consistent' is true ONLY if the right product arrived, in the ordered quantity, "
             'undamaged. JSON shape: {"order_id": string, "product_matches": bool, "ordered_qty": int, "delivered_qty": int, "short_qty": int, '
             '"damaged_qty": int, "consistent": bool, "issues": [strings], "next_action": string}\n\n'
             "ORDER (from our system):\n{order}\n\nDELIVERY NOTE:\n{doc}",
}


def order_for(doc):
    """The order the note refers to, with product names filled in (the model cannot know what 'PB-150' is otherwise)."""
    m = re.search(r"\bA-\d{4}\b", doc)
    if not m:
        raise ValueError("no order reference like A-1003 in the document")
    orders = json.loads((DATA / "orders.json").read_text())
    products = {p["sku"]: p for p in json.loads((DATA / "products.json").read_text())}
    order = next((o for o in orders if o["id"] == m.group()), None)
    if order is None:
        raise ValueError(f"order {m.group()} is not in our system")
    return {**order, "items": [{**i, "name": products.get(i["sku"], {}).get("name")} for i in order["items"]]}


def parse_json(text):
    """Accept a bare object, or one wrapped in ``` fences or <think> text."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the reply")
    return json.loads(text[start:end + 1])


def validate(task, d, order=None):
    """Return a list of problems; empty list = acceptable. Shape checks, then (for check) arithmetic against OUR data."""
    errs = []
    def need(key, *types):
        if key not in d:
            errs.append(f"missing key {key!r}")
        elif not isinstance(d[key], types) or (isinstance(d[key], bool) and bool not in types):
            errs.append(f"{key!r} has the wrong type")
    if task == "summarise":
        need("bullets", list); need("risk_reason", str)
        if isinstance(d.get("bullets"), list) and (len(d["bullets"]) != 3 or not all(isinstance(b, str) and b for b in d["bullets"])):
            errs.append("'bullets' must be exactly 3 non-empty strings")
        if d.get("risk") not in ("low", "medium", "high"):
            errs.append("'risk' must be low, medium or high")
    elif task == "extract":
        for k in ("date", "site", "material", "problem", "unit"):
            need(k, str, type(None))
        need("quantity", int, float, type(None)); need("who_must_act", list)
        if isinstance(d.get("date"), str) and not re.fullmatch(r"\d{4}-\d\d-\d\d", d["date"]):
            errs.append("'date' must be YYYY-MM-DD")
    else:
        need("order_id", str); need("issues", list); need("next_action", str)
        for k in ("product_matches", "consistent"):
            need(k, bool)
        for k in ("ordered_qty", "delivered_qty", "short_qty", "damaged_qty"):
            need(k, int)
        if not errs:
            ordered = sum(i["qty"] for i in order["items"])
            if d["order_id"] != order["id"]:
                errs.append(f"order_id should be {order['id']}")
            if d["ordered_qty"] != ordered:
                errs.append(f"ordered_qty is {d['ordered_qty']} but our order says {ordered}")
            if d["ordered_qty"] - d["delivered_qty"] != d["short_qty"]:
                errs.append("short_qty does not equal ordered_qty - delivered_qty")
            if d["consistent"] and (d["short_qty"] or d["damaged_qty"] or not d["product_matches"]):
                errs.append("'consistent' cannot be true with shortages, damage or the wrong product")
    return errs


def run(task, doc_text, backend=None, max_tokens=1000):
    """Returns (data or None, log). log has one entry per attempt: seconds, raw reply, problems."""
    order = order_for(doc_text) if task == "check" else None
    prompt = PROMPTS[task].replace("{doc}", doc_text).replace("{order}", json.dumps(order, ensure_ascii=False))
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    log = []
    for attempt in (1, 2):
        t = time.time()
        try:
            raw = chat(None, backend=backend, messages=messages, json_mode=True, max_tokens=max_tokens, temperature=0)
        except SystemExit as e:                 # llm.py reports network / key / empty-reply problems this way
            log.append({"attempt": attempt, "seconds": round(time.time() - t, 2), "raw": "", "problems": [str(e)], "fatal": True})
            return None, log
        try:
            data = parse_json(raw)
            problems = validate(task, data, order)
        except ValueError as e:
            data, problems = None, [f"not valid JSON: {e}"]
        log.append({"attempt": attempt, "seconds": round(time.time() - t, 2), "raw": raw, "problems": problems})
        if not problems:
            return data, log
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "That reply was rejected: " + "; ".join(problems) + ". Send the corrected JSON object only."}]
    return None, log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=list(PROMPTS))
    ap.add_argument("--doc", required=True, help="file name in docs/ or a path")
    ap.add_argument("--backend", choices=list(llm.BACKENDS), default=None, help="default: llm.py's DEFAULT_BACKEND")
    ap.add_argument("--max-tokens", type=int, default=1000)
    a = ap.parse_args(argv)
    path = pathlib.Path(a.doc)
    if not path.exists():
        path = DOCS / a.doc
    try:
        data, log = run(a.task, path.read_text(), a.backend, a.max_tokens)
    except (OSError, ValueError) as e:
        sys.exit(f"error: {e}")
    for entry in log:
        if entry["problems"]:
            print(f"attempt {entry['attempt']} rejected: {'; '.join(entry['problems'])}", file=sys.stderr)
    if data is None:
        sys.exit("The model could not be called (see above)." if log[-1].get("fatal") else "No valid answer after one retry. A person must look at this document.")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"# {a.backend or llm.default_backend()} · {len(log)} attempt(s) · {sum(e['seconds'] for e in log):.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
