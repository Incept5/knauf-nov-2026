"""Stretch: a tiny web server that serves index.html and answers /ask?q=... from the CSV with a model.
    python3 ask_server.py --backend local          then open http://localhost:8770
Standard library only. All model settings live in llm.py (copy it next to this file, or it is found in day-1/common)."""
import argparse, csv, json, pathlib, statistics, sys, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
here = pathlib.Path(__file__).resolve().parent
for p in (here, here.parents[2] / "day-1/common"):
    if (p / "llm.py").exists(): sys.path.insert(0, str(p)); break
from llm import chat

CSV = next(p for p in (here / "munich_weather_2025.csv", here.parents[2] / "day-1/ex1-dashboard/munich_weather_2025.csv") if p.exists())
ROWS = list(csv.DictReader(open(CSV)))
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
import datetime as dt
def workable(r): return float(r["rain_mm"]) < 2 and float(r["wind_max_kmh"]) < 40 and float(r["temp_min_c"]) > 0

def facts():
    """A compact, checkable summary of the data that goes into the prompt (cheaper and more reliable than pasting 365 rows)."""
    out = ["Rule: a day is workable if rain < 2 mm, wind < 40 km/h and minimum temperature > 0 C.",
           f"Data: {len(ROWS)} days of Munich weather, {ROWS[0]['date']} to {ROWS[-1]['date']} (historical, NOT a forecast)."]
    out.append("Workable share by weekday: " + ", ".join(
        f"{n} {sum(workable(r) for r in rs)}/{len(rs)}" for i, n in enumerate(DAYS)
        for rs in [[r for r in ROWS if dt.date.fromisoformat(r["date"]).weekday() == i]]))
    for m in range(1, 13):
        rs = [r for r in ROWS if int(r["date"][5:7]) == m]
        out.append(f"Month {m:02d}: {sum(workable(r) for r in rs)}/{len(rs)} workable, rain {sum(float(r['rain_mm']) for r in rs):.0f} mm, "
                   f"coldest night {min(float(r['temp_min_c']) for r in rs)} C")
    out.append("Last 7 days in the data (date, min C, max C, rain mm, wind km/h, workable):")
    out += [f"  {r['date']} {r['temp_min_c']} {r['temp_max_c']} {r['rain_mm']} {r['wind_max_kmh']} {'yes' if workable(r) else 'no'}" for r in ROWS[-7:]]
    return "\n".join(out)

def ask(q, backend):
    prompt = (f"{facts()}\n\nQuestion from a site manager: {q}\n\nAnswer in at most 4 sentences, using only the facts above. "
              "Say plainly that this data is history, not a forecast, and that a real decision needs the forecast for the day. "
              "For concrete, also mention that fresh concrete needs the temperature to stay above about 5 C. Start with a clear yes / no / depends.")
    return chat(prompt, backend=backend, max_tokens=500)

class H(BaseHTTPRequestHandler):
    backend = "local"
    def log_message(self, *a): pass
    def send(self, code, body, ctype):
        b = body.encode(); self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"): return self.send(200, (here / "index.html").read_text(), "text/html")
        if u.path == "/ask":
            q = (urllib.parse.parse_qs(u.query).get("q") or [""])[0][:500]
            try: ans = ask(q, self.backend)
            except SystemExit as e: return self.send(502, json.dumps({"answer": f"Model error: {e}"}), "application/json")  # llm.py exits on errors
            return self.send(200, json.dumps({"answer": ans}), "application/json")
        self.send(404, "not found", "text/plain")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--backend", default="local"); ap.add_argument("--port", type=int, default=8770)
    a = ap.parse_args(); H.backend = a.backend
    print(f"http://localhost:{a.port}  (backend: {a.backend})"); ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
