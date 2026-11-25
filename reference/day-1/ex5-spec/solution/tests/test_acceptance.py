"""One test per acceptance test in ../../SPEC.md.   python3 -m unittest discover -s tests -v   (from solution/)"""
import contextlib, io, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import cli
from pricing import price_order
from storage import load_products

PB = load_products(ROOT / "data/products.json")
big = {"id": "L", "items": [{"sku": "PB-150", "qty": 200}]}
def one(amount):  return price_order({"id": "T", "items": [{"sku": "X", "qty": 1}]}, {"X": {"sku": "X", "name": "x", "unit_price": amount}})


class Acceptance(unittest.TestCase):
    def test_at1_large_order(self):
        r = price_order(big, PB); self.assertEqual((r["discount"], r["net"], r["delivery"], r["gross"]), (124.0, 2356.0, 0.0, 2803.64))
    def test_at2_contract_order(self):
        r = price_order({**big, "contract": True}, PB); self.assertEqual((r["discount"], r["net"], r["gross"]), (0.0, 2281.6, 2715.1))
    def test_at3_exactly_2000(self):
        r = one(2000.0); self.assertEqual((r["discount"], r["gross"]), (0.0, 2380.0))
    def test_at4_one_cent_over(self):
        r = one(2000.01); self.assertEqual((r["discount"], r["net"], r["gross"]), (100.0, 1900.01, 2261.01))
    def test_at5_gross_over_but_net_under(self):
        self.assertEqual(one(1990.0)["discount"], 0.0)
    def test_at6_shipped_orders_unchanged(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): cli.main(ROOT / "data/orders.json")
        self.assertEqual(out.getvalue().splitlines(), [
            "Order A-1001: net 371.00  delivery 45.00  VAT 79.04  total 495.04",
            "Order A-1002: net 566.35  delivery 0.00  VAT 107.61  total 673.96",
            "Order A-1003: net 620.00  delivery 0.00  VAT 117.80  total 737.80",
            "Order A-1004: NOT PRICED  (unknown SKU XX-999)"])
    def test_req7_cli_shows_discount(self):
        self.assertIn("discount -124.00", cli.format_result(price_order(big, PB)))


if __name__ == "__main__":
    unittest.main()
