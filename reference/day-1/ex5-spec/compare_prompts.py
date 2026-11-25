"""The real comparison: the same model gets (a) one plain sentence, (b) the spec. Each answer is saved in runs/, applied to a
copy of base/ and scored on behaviour only (amount payable), so neither version is punished for choosing different key names.
    python3 compare_prompts.py --label mlx-27b      model chosen with LLM_LOCAL_BASE / LLM_LOCAL_MODEL (see llm.py)"""
import argparse, json, pathlib, re, shutil, subprocess, sys, tempfile, time
HERE = pathlib.Path(__file__).resolve().parent
for p in (HERE, HERE.parents[2] / "day-1/common"):
    if (p / "llm.py").exists(): sys.path.insert(0, str(p)); break
from llm import chat

files = "".join(f"\n=== {n} ===\n{(HERE / 'base' / n).read_text()}" for n in ("pricing.py", "storage.py", "cli.py"))
FORMAT = "\n\nReply with the COMPLETE new content of every file you change, each as a ```python block whose first line is `# file: NAME`."
PROMPTS = {"plain": "Add a 5% discount for orders over 2,000 EUR, but not for orders that already have the contract rate." + FORMAT + "\n" + files,
           "spec": "Implement this specification in the code below. Do not write the tests.\n\n" + (HERE / "SPEC.md").read_text() + FORMAT + "\n" + files}
SCORE = r'''
import json, sys, subprocess, pathlib
from pricing import price_order
from storage import load_products
PB = load_products("data/products.json")
def gross(qty=None, contract=False, amount=None):
    p = PB if amount is None else {"X": {"sku": "X", "name": "x", "unit_price": amount}}
    o = {"id": "T", "items": [{"sku": "PB-150", "qty": qty}] if amount is None else [{"sku": "X", "qty": 1}]}
    if contract: o["contract"] = True
    return price_order(o, p)["gross"]
cases = [("2480 gets discount", dict(qty=200), 2803.64), ("contract gets none", dict(qty=200, contract=True), 2715.10),
         ("exactly 2000: none", dict(amount=2000.0), 2380.00), ("2000.01: discount", dict(amount=2000.01), 2261.01),
         ("1990 net (gross>2000): none", dict(amount=1990.0), 2368.10), ("small order unchanged", dict(amount=100.0), 172.55)]
for name, kw, want in cases:
    try: got = gross(**kw); print(("PASS" if abs(got - want) < 0.005 else "FAIL"), name, got, want)
    except Exception as e: print("FAIL", name, type(e).__name__, e)
big = pathlib.Path("big.json"); big.write_text(json.dumps([{"id": "L", "items": [{"sku": "PB-150", "qty": 200}]}]))
out = subprocess.run([sys.executable, "cli.py", "big.json"], capture_output=True, text=True).stdout
print("PASS" if "discount" in out.lower() else "FAIL", "CLI shows the discount:", out.strip())
'''

def score(reply):
    d = pathlib.Path(tempfile.mkdtemp()); shutil.copytree(HERE / "base", d, dirs_exist_ok=True); shutil.copytree(HERE / "solution/data", d / "data")
    changed = []
    # Models do not always keep the requested format (some omit the ``` fences), so split on the "# file:" markers.
    parts = re.split(r"^# file:\s*([\w.]+\.py)\s*$", reply, flags=re.M)
    for name, block in zip(parts[1::2], parts[2::2]):
        block = re.sub(r"\A\s*```(?:python)?[ \t]*\n", "", block)      # fence AFTER the marker
        block = re.split(r"^```", block, flags=re.M)[0]                   # everything up to the closing fence
        (d / name).write_text(block); changed.append(name)
    (d / "_score.py").write_text(SCORE)
    r = subprocess.run([sys.executable, "_score.py"], cwd=d, capture_output=True, text=True, timeout=60)
    return changed, (r.stdout + r.stderr[-600:]).strip()

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--label", required=True); ap.add_argument("--backend", default="local"); ap.add_argument("--reps", type=int, default=3); ap.add_argument("--rescore", action="store_true", help="re-score the saved replies, no model calls")
    a = ap.parse_args(); (HERE / "runs").mkdir(exist_ok=True)
    for kind, prompt in PROMPTS.items():
        for rep in range(a.reps):
            saved = HERE / "runs" / f"{a.label}-{kind}-{rep}.md"
            if a.rescore:
                reply, tail = saved.read_text().rsplit("\n\n---\n", 1); secs = float(tail.split("s,")[0])
            else:
                t = time.time()
                reply = chat(prompt, backend=a.backend, max_tokens=4000, temperature=0 if rep == 0 else 0.7); secs = time.time() - t
            changed, result = score(reply)
            (HERE / "runs" / f"{a.label}-{kind}-{rep}.md").write_text(f"{reply}\n\n---\n{secs:.1f}s, files changed: {changed}\n\n{result}\n")
            print(f"{a.label} {kind:5} rep{rep} {secs:5.1f}s changed={changed} passed {len(re.findall('^PASS', result, re.M))}/7")
            for line in result.splitlines():
                if not line.startswith("PASS"): print("      ", line)
