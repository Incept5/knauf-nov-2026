"""Delivery tracker for a building-materials supplier: reference for the live demo. Python standard library only.
    python3 app.py --seed            then open http://localhost:8780      (--offline to force no internet, --db FILE, --port N)
    python3 -m unittest -v           tests"""
import argparse, csv, datetime as dt, json, pathlib, re, sqlite3, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
LAT, LON = 48.137, 11.575                                  # Munich
FORECAST = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&timezone=Europe%2FBerlin&past_days=31&forecast_days=16"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max")


def status(expected, delivered_on, today):
    if delivered_on: return "delivered"
    if expected < today: return "late"
    return "today" if expected == today else "upcoming"


def validate(d):
    """Return (clean row, None) or (None, error code). Codes are translated by the page."""
    if not isinstance(d, dict): return None, "bad_request"
    clean = {}
    for k in ("supplier", "material", "site"):
        v = str(d.get(k) or "").strip()
        if not v: return None, f"missing_{k}"
        clean[k] = v[:200]
    try:
        clean["qty"] = int(str(d.get("qty", "")).strip())
        if not 0 < clean["qty"] <= 1_000_000: raise ValueError
    except ValueError:
        return None, "bad_qty"
    v = str(d.get("expected") or "").strip()
    if not v: return None, "missing_date"
    try:
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", v): raise ValueError
        dt.date.fromisoformat(v)
    except ValueError:
        return None, "bad_date"
    clean["expected"] = v
    return clean, None


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as c:
            c.execute("CREATE TABLE IF NOT EXISTS deliveries (id INTEGER PRIMARY KEY, supplier TEXT NOT NULL, material TEXT NOT NULL,"
                      " qty INTEGER NOT NULL, expected TEXT NOT NULL, site TEXT NOT NULL, delivered_on TEXT)")

    def db(self):
        con = sqlite3.connect(self.path, timeout=5); con.row_factory = sqlite3.Row
        class Ctx:                                        # commit AND close (sqlite3's own context manager does not close)
            def __enter__(_): return con
            def __exit__(_, et, *a):
                con.rollback() if et else con.commit(); con.close()
        return Ctx()

    def add(self, row):
        with self.db() as c:
            return c.execute("INSERT INTO deliveries (supplier, material, qty, expected, site) VALUES (:supplier,:material,:qty,:expected,:site)", row).lastrowid

    def list(self, today):
        with self.db() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM deliveries")]
        for r in rows: r["status"] = status(r["expected"], r["delivered_on"], today)
        order = {"late": 0, "today": 1, "upcoming": 2, "delivered": 3}
        return sorted(rows, key=lambda r: (order[r["status"]], r["expected"], r["id"]))

    def set_delivered(self, id, on):
        with self.db() as c:
            return c.execute("UPDATE deliveries SET delivered_on=? WHERE id=?", (on, id)).rowcount > 0

    def delete(self, id):
        with self.db() as c:
            return c.execute("DELETE FROM deliveries WHERE id=?", (id,)).rowcount > 0

    def seed(self, today):
        if self.list(today.isoformat()): return
        day = lambda n: (today + dt.timedelta(n)).isoformat()
        for s, m, q, e, site in [("Alpenbau Baustoffe", "Plasterboard 15 mm fire-rated", 50, day(-2), "Schulzentrum Nord"),
                                 ("Isar Trockenbau", "Plasterboard 12.5 mm", 120, day(0), "Wohnanlage Lindenhof"),
                                 ("Alpenbau Baustoffe", "Jointing compound 25 kg", 16, day(1), "Wohnanlage Lindenhof"),
                                 ("Bavaria Dämmstoffe", "Mineral wool 100 mm (m2)", 300, day(5), "Schulzentrum Nord"),
                                 ("Isar Trockenbau", "Drywall screws 500 pcs", 20, day(-4), "Kita Pasing")]:
            i = self.add({"supplier": s, "material": m, "qty": q, "expected": e, "site": site})
            if "screws" in m: self.set_delivered(i, day(-4))


class Weather:
    """Live Open-Meteo forecast, cached; if there is no internet, last year's weather for the same date, clearly labelled."""
    def __init__(self, offline=False):
        self.offline, self.live, self.fetched, self.failed = offline, {}, 0.0, 0.0
        with open(HERE / "munich_weather_2025.csv") as f:
            self.last_year = {r["date"][5:]: r for r in csv.DictReader(f)}

    def refresh(self):
        now = time.time()
        if self.offline or now - self.fetched < 1800 or now - self.failed < 60: return     # do not hang every request when offline
        try:
            with urllib.request.urlopen(FORECAST, timeout=3) as r:
                d = json.load(r)["daily"]
            self.live = {day: {"tmin": d["temperature_2m_min"][i], "tmax": d["temperature_2m_max"][i], "rain": d["precipitation_sum"][i],
                               "wind": d["wind_speed_10m_max"][i]} for i, day in enumerate(d["time"])}
            self.fetched = now
        except Exception:                                  # DNS, proxy (Zscaler), timeout, bad JSON: all mean "use the fallback"
            self.failed = now

    def for_dates(self, dates):
        self.refresh()
        out = {}
        for day in dates:
            w = self.live.get(day)
            if w and None not in w.values():
                out[day] = {**w, "source": "live"}
                continue
            r = self.last_year.get(day[5:])
            if r:
                out[day] = {"tmin": float(r["temp_min_c"]), "tmax": float(r["temp_max_c"]), "rain": float(r["rain_mm"]),
                            "wind": float(r["wind_max_kmh"]), "source": "last_year"}
        for w in out.values():
            w["workable"] = w["rain"] < 2 and w["wind"] < 40 and w["tmin"] > 0
        return out


def make_handler(store, weather, today=lambda: dt.date.today()):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def send(self, code, obj, ctype="application/json"):
            b = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self.send(200, (HERE / "index.html").read_bytes(), "text/html")
            if self.path == "/api/deliveries":
                rows = store.list(today().isoformat())
                return self.send(200, {"today": today().isoformat(), "deliveries": rows, "weather": weather.for_dates({r["expected"] for r in rows})})
            self.send(404, {"error": "not_found"})

        def do_POST(self):
            # Only JSON is accepted: another website cannot send it cross-origin without a pre-flight this server never answers.
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self.send(415, {"error": "bad_request"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if not 0 <= n <= 10_000: raise ValueError
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self.send(400, {"error": "bad_request"})
            if self.path == "/api/deliveries":
                row, err = validate(body)
                return self.send(400, {"error": err}) if err else self.send(201, {"id": store.add(row)})
            m = re.fullmatch(r"/api/deliveries/(\d{1,15})/(delivered|undo|delete)", self.path)
            if m:
                i, action = int(m[1]), m[2]
                ok = store.delete(i) if action == "delete" else store.set_delivered(i, today().isoformat() if action == "delivered" else None)
                return self.send(200 if ok else 404, {"ok": ok})
            self.send(404, {"error": "not_found"})
    return H


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8780); ap.add_argument("--db", default=str(HERE / "deliveries.db"))
    ap.add_argument("--seed", action="store_true", help="add example deliveries if the database is empty")
    ap.add_argument("--offline", action="store_true", help="never call Open-Meteo")
    ap.add_argument("--lan", action="store_true", help="also reachable from phones on the same Wi-Fi (no login: demo only)")
    a = ap.parse_args()
    store = Store(a.db)
    if a.seed: store.seed(dt.date.today())
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    print(f"Delivery tracker on http://localhost:{a.port}   (Ctrl+C to stop)")
    ThreadingHTTPServer((host, a.port), make_handler(store, Weather(a.offline))).serve_forever()
