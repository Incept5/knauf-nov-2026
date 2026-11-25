"""Runs all three tasks on all three documents with one model and records time, tokens, validity and raw replies.
    python3 bench.py --label ollama-9b            (model chosen with LLM_LOCAL_BASE / LLM_LOCAL_MODEL, as in llm.py)"""
import argparse, json, pathlib, time
import ai_features as ai
import llm

usage = []
_orig = llm._post
def _post(name, b, path, body):
    data = _orig(name, b, path, body)
    if data and "usage" in data: usage.append(data["usage"])
    return data
llm._post = _post

DOCS = ["delivery_note.txt", "site_incident_report.txt", "datasheet_excerpt.txt"]
CASES = [(t, d) for t in ("summarise", "extract") for d in DOCS] + [("check", "delivery_note.txt")]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--backend", default="local"); ap.add_argument("--label", required=True); ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()
    out = {"label": a.label, "model": llm.settings(a.backend)["model"], "cases": []}
    llm.chat("Reply with the single word: ok", backend=a.backend, max_tokens=300)      # warm up: do not time model loading
    for rep in range(a.repeat):
        for task, doc in CASES:
            usage.clear(); t = time.time()
            data, log = ai.run(task, (ai.DOCS / doc).read_text(), a.backend)
            out["cases"].append({"rep": rep, "task": task, "doc": doc, "seconds": round(time.time() - t, 2), "attempts": len(log),
                                 "valid": data is not None, "usage": list(usage), "data": data, "log": log})
            print(f"{a.label:14} {task:9} {doc:26} {out['cases'][-1]['seconds']:6.1f}s attempts={len(log)} valid={data is not None}", flush=True)
    pathlib.Path(__file__).parent.joinpath("runs", f"{a.label}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
