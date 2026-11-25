"""Can a model find the three seeded bugs from the attendee code alone?   python3 bughunt.py --label x   (model: LLM_LOCAL_* variables)"""
import argparse, pathlib, sys, time
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "day-1/common"))
sys.dont_write_bytecode = True
from llm import chat
SRC = HERE.parents[2] / "day-1/ex2-existing-code/order_pricing"
code = "".join(f"\n=== {n} ===\n{(SRC / n).read_text()}" for n in ("pricing.py", "cli.py", "data/orders.json", "data/products.json"))
ap = argparse.ArgumentParser(); ap.add_argument("--label", required=True); ap.add_argument("--backend", default="local"); a = ap.parse_args()
(HERE / "runs").mkdir(exist_ok=True)
for rep in range(2):
    t = time.time()
    r = chat("This tool has bugs. List each bug you are confident of, one short line each, most serious first.\n" + code, backend=a.backend, max_tokens=1500, temperature=0 if rep == 0 else 0.7)
    (HERE / "runs" / f"bughunt-{a.label}-{rep}.md").write_text(r + f"\n\n---\n{time.time() - t:.1f}s\n")
    print(a.label, rep, f"{time.time() - t:.1f}s")
