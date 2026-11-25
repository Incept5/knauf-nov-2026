"""Tests for order_pricing. They run against the fixed code by default, and against ANY version with
    PRICING_DIR=/path/to/order_pricing python3 -m unittest discover -s tests -v
so you can show they FAIL on the original (3 bugs + the new feature) and PASS on the reference solution."""
import importlib.util, json, os, pathlib, unittest

HERE = pathlib.Path(__file__).resolve().parent
DIR = pathlib.Path(os.environ.get("PRICING_DIR", HERE.parent)).resolve()
spec = importlib.util.spec_from_file_location("pricing_under_test", DIR / "pricing.py")
pricing = importlib.util.module_from_spec(spec); spec.loader.exec_module(pricing)
PRODUCTS = {p["sku"]: p for p in json.load(open(DIR / "data" / "products.json"))}
price = lambda order: pricing.price_order(order, PRODUCTS)
order = lambda items, contract=False, id="T": {"id": id, "items": [{"sku": s, "qty": q} for s, q in items], **({"contract": True} if contract else {})}


class BugFixes(unittest.TestCase):
    def test_contract_price_is_a_discount_not_a_multiplier(self):          # bug 1
        r = price(order([("INS-100", 80)], contract=True))                  # list 80 x 6.75 = 540.00, contract 8% off = 496.80
        self.assertEqual(r["net"], 496.80)

    def test_contract_line_total(self):
        self.assertEqual(pricing.line_total(PRODUCTS["JT-25"], 4, True), 69.55)   # 4 x 18.90 x 0.92 = 69.552

    def test_free_delivery_at_exactly_500(self):                            # bug 2
        p = {"X": {"sku": "X", "name": "x", "unit_price": 500.0}}
        r = pricing.price_order(order([("X", 1)]), p)
        self.assertEqual((r["net"], r["delivery"]), (500.0, 0.0))

    def test_delivery_fee_just_below_500(self):
        self.assertEqual(pricing.delivery_fee(499.99), 45.0)
        self.assertEqual(pricing.delivery_fee(500.01), 0.0)

    def test_unknown_sku_does_not_crash_the_run(self):                      # bug 3
        orders = [order([("PB-125", 10)], id="A"), order([("XX-999", 1)], id="B"), order([("PB-150", 50)], id="C")]
        results = [price(o) for o in orders]                                 # must not raise
        self.assertEqual([r["order"] for r in results], ["A", "B", "C"])
        self.assertNotIn(results[1].get("status", "ok"), ("ok",))           # the bad order is flagged, not silently priced
        self.assertEqual(results[2]["net"], 620.0)                           # later orders are unaffected


class Baseline(unittest.TestCase):
    def test_plain_order(self):                                              # A-1001: 40 x 8.90 + 2 x 7.50 = 371.00, +45 delivery
        r = price(order([("PB-125", 40), ("SC-500", 2)]))
        self.assertEqual((r["net"], r["delivery"], r["vat"], r["gross"]), (371.0, 45.0, 79.04, 495.04))

    def test_vat_is_19_percent_of_net_plus_delivery(self):
        r = price(order([("PB-150", 50)]))                                   # 620.00 net, free delivery
        self.assertEqual((r["net"], r["delivery"], r["vat"], r["gross"]), (620.0, 0.0, 117.8, 737.8))


class VolumeDiscount(unittest.TestCase):                                     # the new 5% rule
    def test_over_2000_gets_5_percent(self):
        r = price(order([("PB-150", 200)]))                                  # 2480.00
        self.assertEqual((r["discount"], r["net"], r["delivery"], r["gross"]), (124.0, 2356.0, 0.0, 2803.64))

    def test_contract_order_over_2000_gets_no_extra_discount(self):
        r = price(order([("PB-150", 200)], contract=True))                   # 2480 x 0.92 = 2281.60
        self.assertEqual((r["discount"], r["net"]), (0.0, 2281.60))

    def test_exactly_2000_gets_no_discount(self):                            # "over 2,000" means strictly over
        p = {"X": {"sku": "X", "name": "x", "unit_price": 2000.0}}
        r = pricing.price_order(order([("X", 1)]), p)
        self.assertEqual((r["discount"], r["net"]), (0.0, 2000.0))

    def test_one_cent_over_2000_gets_discount(self):
        p = {"X": {"sku": "X", "name": "x", "unit_price": 2000.01}}
        r = pricing.price_order(order([("X", 1)]), p)
        self.assertEqual((r["discount"], r["net"]), (100.0, 1900.01))

    def test_threshold_uses_goods_net_before_delivery(self):                 # 1,990 goods + nothing: no discount even though VAT-inclusive > 2,000
        p = {"X": {"sku": "X", "name": "x", "unit_price": 1990.0}}
        self.assertEqual(pricing.price_order(order([("X", 1)]), p)["discount"], 0.0)


class Separation(unittest.TestCase):
    def test_pricing_module_has_no_file_or_cli_code(self):
        src = (DIR / "pricing.py").read_text()
        for word in ("import json", "open(", "print(", "sys.argv"):
            self.assertNotIn(word, src, f"pricing.py should be pure logic but contains {word!r}")


if __name__ == "__main__":
    unittest.main()
