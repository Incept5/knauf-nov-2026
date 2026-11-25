import datetime as dt, json, pathlib, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
import app

TODAY = dt.date(2026, 11, 26)
GOOD = {"supplier": "S", "material": "Plasterboard", "qty": "10", "expected": "2026-11-26", "site": "Nord"}


class Rules(unittest.TestCase):
    def test_status(self):
        self.assertEqual(app.status("2026-11-25", None, "2026-11-26"), "late")
        self.assertEqual(app.status("2026-11-26", None, "2026-11-26"), "today")
        self.assertEqual(app.status("2026-11-27", None, "2026-11-26"), "upcoming")
        self.assertEqual(app.status("2026-11-01", "2026-11-26", "2026-11-26"), "delivered")

    def test_validate(self):
        self.assertIsNone(app.validate(GOOD)[1])
        for change, code in [({"expected": ""}, "missing_date"), ({"expected": "2026-02-30"}, "bad_date"), ({"expected": "20261126"}, "bad_date"),
                             ({"qty": "0"}, "bad_qty"), ({"qty": "1.5"}, "bad_qty"), ({"site": "  "}, "missing_site")]:
            self.assertEqual(app.validate({**GOOD, **change})[1], code, change)

    def test_offline_weather_is_labelled(self):
        w = app.Weather(offline=True).for_dates(["2026-11-26"])["2026-11-26"]
        self.assertEqual(w["source"], "last_year")

    def test_broken_network_falls_back(self):
        w, real = app.Weather(), app.urllib.request.urlopen
        app.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("blocked"))
        try:
            self.assertEqual(w.for_dates(["2026-11-26"])["2026-11-26"]["source"], "last_year")
        finally:
            app.urllib.request.urlopen = real


class Http(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        h = app.make_handler(app.Store(pathlib.Path(self.tmp.name) / "t.db"), app.Weather(offline=True), today=lambda: TODAY)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), h)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.tmp.cleanup()

    def req(self, path, body=None, ctype="application/json"):
        r = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": ctype})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if resp.headers["Content-Type"].startswith("application/json") else raw
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_add_deliver_undo_delete(self):
        code, out = self.req("/api/deliveries", {**GOOD, "expected": "2026-11-20"}); self.assertEqual(code, 201)
        first = lambda: self.req("/api/deliveries")[1]["deliveries"]
        self.assertEqual(first()[0]["status"], "late")
        self.req(f"/api/deliveries/{out['id']}/delivered", {}); self.assertEqual(first()[0]["status"], "delivered")
        self.req(f"/api/deliveries/{out['id']}/undo", {}); self.assertEqual(first()[0]["status"], "late")
        self.req(f"/api/deliveries/{out['id']}/delete", {}); self.assertEqual(first(), [])

    def test_delivery_without_a_date_is_rejected(self):          # the "break it on purpose" step of the demo
        self.assertEqual(self.req("/api/deliveries", {**GOOD, "expected": ""}), (400, {"error": "missing_date"}))

    def test_non_json_post_is_rejected(self):
        self.assertEqual(self.req("/api/deliveries", GOOD, ctype="text/plain")[0], 415)

    def test_page_and_missing(self):
        self.assertIn(b"Delivery tracker", self.req("/")[1])
        self.assertEqual(self.req("/api/deliveries/999/delivered", {})[0], 404)


if __name__ == "__main__":
    unittest.main()
