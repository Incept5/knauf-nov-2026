"""Exercise 4, round 2: what does 100,000 rows cost the dashboard LOGIC?   python3 perf_100k.py [rows]
Times the pure-Python equivalent and, if Node is installed, the page's real CORE JavaScript on the same generated CSV."""
import csv, datetime as dt, io, pathlib, random, shutil, subprocess, sys, tempfile, time
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
random.seed(1)
buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n")
w.writerow("date temp_max_c temp_min_c rain_mm wind_max_kmh sunshine_hours".split())
start = dt.date(1800, 1, 1)
for i in range(N):
    lo = random.uniform(-10, 20)
    w.writerow([start + dt.timedelta(i), round(lo + random.uniform(1, 12), 1), round(lo, 1), round(max(0, random.gauss(0, 4)), 2), round(random.uniform(2, 50), 1), round(random.uniform(0, 14), 1)])
text = buf.getvalue()
def timed(label, fn):
    t = time.perf_counter(); r = fn(); print(f"  {label:32} {1000 * (time.perf_counter() - t):7.0f} ms"); return r
print(f"{N:,} rows, {len(text) / 1e6:.1f} MB of CSV\nPython equivalent:")
rows = timed("parse CSV", lambda: list(csv.DictReader(io.StringIO(text))))
bad = timed("classify every day", lambda: [not (float(r["rain_mm"]) < 2 and float(r["wind_max_kmh"]) < 40 and float(r["temp_min_c"]) > 0) for r in rows])
timed("filter months 1-3", lambda: [r for r in rows if "01" <= r["date"][5:7] <= "03"])
def months():
    out = {}
    for r, b in zip(rows, bad): out.setdefault(r["date"][5:7], [0, 0])[b] += 1
    return out
timed("monthly summary", months)
def weeks():                                   # one pass: group by ISO week, then sort (not: search 7 days per row)
    g = {}
    for r, b in zip(rows, bad):
        k = dt.date.fromisoformat(r["date"]).isocalendar()[:2]; x = g.setdefault(k, [0, 0, 0.0]); x[0] += 1; x[1] += b; x[2] += float(r["rain_mm"])
    return sorted((x for x in g.values() if x[0] == 7), key=lambda x: (-x[1], -x[2]))[:5]
timed("five worst weeks", weeks)
if shutil.which("node"):
    f = pathlib.Path(tempfile.mkdtemp()) / "big.csv"; f.write_text(text)
    js = """const fs=require('fs'),h=fs.readFileSync(process.argv[1],'utf8'),m={exports:{}};new Function('module',h.match(/<script id="core">([\\s\\S]*?)<\\/script>/)[1])(m);
const E=m.exports,csv=fs.readFileSync(process.argv[2],'utf8');const T=(l,f)=>{const t=performance.now(),r=f();console.log('  '+l.padEnd(32)+String(Math.round(performance.now()-t)).padStart(7)+' ms');return r};
const rows=T('parse + classify',()=>E.prepare(E.parseCSV(csv)));T('filter months 1-3',()=>E.inRange(rows,1,3));T('monthly summary',()=>E.monthly(rows));T('five worst weeks',()=>E.worstWeeks(rows));"""
    print("The dashboard's own JavaScript (Node):", flush=True)
    subprocess.run(["node", "-e", js, str(pathlib.Path(__file__).parent / "../ex1-dashboard/index.html"), str(f)], check=True)
    print("CSV written to", f, "(load it with the page's file picker to see what DRAWING 100,000 points does)")
