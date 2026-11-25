"""Command line: python3 cli.py [orders.json]   (works from any folder)"""
import pathlib
import sys
from pricing import price_order
from storage import load_orders, load_products

HERE = pathlib.Path(__file__).resolve().parent


def format_result(r):
    if r["status"] != "ok":
        return f"Order {r['order']}: NOT PRICED  ({'; '.join(r['errors'])})"
    disc = f"  discount -{r['discount']:.2f}" if r["discount"] else ""
    return (f"Order {r['order']}: net {r['net']:.2f}{disc}  delivery {r['delivery']:.2f}  "
            f"VAT {r['vat']:.2f}  total {r['gross']:.2f}")


def main(path):
    products = load_products(HERE / "data" / "products.json")
    results = [price_order(o, products) for o in load_orders(path)]
    for r in results:
        print(format_result(r))
    return 1 if any(r["status"] != "ok" for r in results) else 0     # non-zero exit if any order could not be priced


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else HERE / "data" / "orders.json"))
