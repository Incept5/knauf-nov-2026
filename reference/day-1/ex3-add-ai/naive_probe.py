"""What goes wrong with a lazy prompt (no schema, no definition, raw order file without product names).
    python3 naive_probe.py --label mlx-27b      (model chosen with the LLM_LOCAL_* variables)"""
import argparse, json, pathlib, time
import ai_features as ai
import llm
note = (ai.DOCS / "delivery_note.txt").read_text()
orders = (ai.DATA / "orders.json").read_text()
PROBES = {"naive-check": f"Is this delivery note consistent with the order? Reply as JSON.\n\nORDERS:\n{orders}\n\nNOTE:\n{note}",
          "naive-extract": "Extract as JSON: date, site, material, quantity, problem, who must act.\n\n" + (ai.DOCS / "site_incident_report.txt").read_text()}
ap = argparse.ArgumentParser(); ap.add_argument("--label", required=True); ap.add_argument("--backend", default="local"); a = ap.parse_args()
out = []
for name, p in PROBES.items():
    for rep in range(3):
        t = time.time()
        try: raw = llm.chat(p, backend=a.backend, temperature=0.7 if rep else 0, max_tokens=1000)     # no json_mode on purpose
        except SystemExit as e: raw = f"ERROR {e}"
        out.append({"probe": name, "rep": rep, "seconds": round(time.time() - t, 2), "raw": raw})
        print(a.label, name, rep, out[-1]["seconds"], "fenced" if raw.startswith("```") else "bare" if raw.startswith("{") else "prose-first", flush=True)
pathlib.Path(__file__).parent.joinpath("runs", f"naive-{a.label}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
