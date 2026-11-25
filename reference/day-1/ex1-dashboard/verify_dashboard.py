"""Independent recomputation of the dashboard numbers; fails if the JS (run with Node) disagrees.   python3 verify_dashboard.py"""
import csv, datetime as dt, json, subprocess, sys, pathlib
here = pathlib.Path(__file__).parent
src = here / "../../../day-1/ex1-dashboard/munich_weather_2025.csv"
rows = list(csv.DictReader(open(src)))
def check(m1, m2):
    sel = [r for r in rows if m1 <= int(r["date"][5:7]) <= m2]
    bad = lambda r: not (float(r["rain_mm"]) < 2 and float(r["wind_max_kmh"]) < 40 and float(r["temp_min_c"]) > 0)
    s = {"days": len(sel), "ok": sum(not bad(r) for r in sel), "bad": sum(bad(r) for r in sel)}
    mon = {}
    for r in sel: mon.setdefault(int(r["date"][5:7]), [0, 0]); mon[int(r["date"][5:7])][bad(r)] += 1
    by = {dt.date.fromisoformat(r["date"]): r for r in sel}
    weeks = []
    for d in by:
        if d.weekday() == 0 and all(d + dt.timedelta(i) in by for i in range(7)):
            w = [by[d + dt.timedelta(i)] for i in range(7)]
            weeks.append((-sum(bad(x) for x in w), -round(sum(float(x["rain_mm"]) for x in w), 1), min(float(x["temp_min_c"]) for x in w), d.isoformat()))
    weeks.sort()
    js = json.loads(subprocess.check_output(["node", str(here / "verify_dashboard.js"), str(src), str(m1), str(m2)]))
    assert (js["summary"]["days"], js["summary"]["ok"], js["summary"]["bad"]) == (s["days"], s["ok"], s["bad"]), (js["summary"], s)
    assert {o["month"]: [o["ok"], o["bad"]] for o in js["monthly"]} == mon
    assert [(w["start"], w["bad"]) for w in js["worst"]] == [(w[3], -w[0]) for w in weeks[:5]], (js["worst"], weeks[:5])
    return s, weeks[:5]
for rng in [(1, 12), (1, 3), (6, 8), (12, 12)]:
    s, w = check(*rng); print(rng, s, "OK")
print("worst weeks (full range):", [(w[3], -w[0], -w[1]) for w in check(1, 12)[1]])
print("JS and Python agree.")
