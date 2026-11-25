"""Applies each saved model reply (runs/*.md) to a copy of base/ and runs the spec's acceptance tests on it."""
import pathlib, re, shutil, subprocess, sys, tempfile
import compare_prompts as cp
HERE = pathlib.Path(__file__).resolve().parent
for run in sorted((HERE / "runs").glob("*.md")):
    d = pathlib.Path(tempfile.mkdtemp()); shutil.copytree(HERE / "base", d, dirs_exist_ok=True); shutil.copytree(HERE / "solution/data", d / "data"); shutil.copytree(HERE / "solution/tests", d / "tests")
    parts = re.split(r"^# file:\s*([\w.]+\.py)\s*$", run.read_text().rsplit("\n\n---\n", 1)[0], flags=re.M)
    for name, block in zip(parts[1::2], parts[2::2]):
        (d / name).write_text(re.split(r"^```", re.sub(r"\A\s*```(?:python)?[ \t]*\n", "", block), flags=re.M)[0])
    out = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=d, capture_output=True, text=True).stderr
    bad = [l.split()[0] for l in out.splitlines() if l.endswith(("FAIL", "ERROR"))]
    print(f"{run.stem:22} {7 - len(bad)}/7 acceptance tests", bad)
