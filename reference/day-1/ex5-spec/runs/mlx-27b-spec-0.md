# file: pricing.py
"""Prices an order of building materials. Pure logic: no files, no printing, no command line (see storage.py and cli.py)."""

VAT_RATE = 0.19
FREE_DELIVERY_FROM = 500.0        # net goods value at or above which delivery is free (FIX 2: was "over", so exactly 500 paid)
DELIVERY_FEE = 45.0
CONTRACT_DISCOUNT = 0.08          # contract customers pay 92% of list price
VOLUME_DISCOUNT_THRESHOLD = 2000.0 # goods value strictly greater than this gets a volume discount
VOLUME_DISCOUNT_RATE = 0.05       # 5% off goods value for large non-contract orders


class UnknownSku(Exception):
    """An order line names a product that is not in the catalogue."""


def line_total(product, quantity, contract):
    price = product["unit_price"]
    if contract:
        price = price * (1 - CONTRACT_DISCOUNT)   # FIX 1: was price * 0.08, which charged 8% of the price
    return round(price * quantity, 2)


def delivery_fee(net_total):
    return 0.0 if net_total >= FREE_DELIVERY_FROM else DELIVERY_FEE


def price_order(order, products):
    """Price one order. Never raises for bad catalogue data: an order with an unknown SKU comes back with
    status "error" and the reasons, so one bad order cannot stop a whole run (FIX 3)."""
    contract = order.get("contract", False)
    lines, unknown = [], []
    for item in order["items"]:
        product = products.get(item["sku"])
        if product is None:
            unknown.append(item["sku"])
            continue
        lines.append({"sku": item["sku"], "name": product["name"], "qty": item["qty"],
                      "total": line_total(product, item["qty"], contract)})
    if unknown:
        return {"order": order["id"], "status": "error", "errors": [f"unknown SKU {s}" for s in unknown],
                "lines": lines, "net": None, "delivery": None, "vat": None, "gross": None, "discount": 0.0}
    
    goods_value = round(sum(l["total"] for l in lines), 2)
    
    # Volume discount: only for non-contract orders where goods value is strictly greater than threshold
    discount = 0.0
    if not contract and goods_value > VOLUME_DISCOUNT_THRESHOLD:
        discount = round(goods_value * VOLUME_DISCOUNT_RATE, 2)
    
    net = round(goods_value - discount, 2)
    fee = delivery_fee(net)
    vat = round((net + fee) * VAT_RATE, 2)
    return {"order": order["id"], "status": "ok", "errors": [], "lines": lines,
            "net": net, "delivery": fee, "vat": vat, "gross": round(net + fee + vat, 2), "discount": discount}

# file: cli.py
"""Command line: python3 cli.py [orders.json]   (works from any folder)"""
import pathlib
import sys
from pricing import price_order
from storage import load_orders, load_products

HERE = pathlib.Path(__file__).resolve().parent


def format_result(r):
    if r["status"] != "ok":
        return f"Order {r['order']}: NOT PRICED  ({'; '.join(r['errors'])})"
    base = (f"Order {r['order']}: net {r['net']:.2f}  delivery {r['delivery']:.2f}  "
            f"VAT {r['vat']:.2f}  total {r['gross']:.2f}")
    if r["discount"] > 0:
        base += f"  discount -{r['discount']:.2f}"
    return base


def main(path):
    products = load_products(HERE / "data" / "products.json")
    results = [price_order(o, products) for o in load_orders(path)]
    for r in results:
        print(format_result(r))
    return 1 if any(r["status"] != "ok" for r in results) else 0     # non-zero exit if any order could not be priced


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else HERE / "data" / "orders.json"))

---
77.1s, files changed: ['pricing.py', 'cli.py']

PASS 2480 gets discount 2803.64 2803.64
PASS contract gets none 2715.1 2715.1
PASS exactly 2000: none 2380.0 2380.0
PASS 2000.01: discount 2261.01 2261.01
PASS 1990 net (gross>2000): none 2368.1 2368.1
PASS small order unchanged 172.55 172.55
PASS CLI shows the discount: Order L: net 2356.00  delivery 0.00  VAT 447.64  total 2803.64  discount -124.00
