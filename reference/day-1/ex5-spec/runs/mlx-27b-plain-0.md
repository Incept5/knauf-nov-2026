To implement the 5% discount for orders over 2,000 EUR (excluding those with contract rates), I need to modify `pricing.py`.

1.  **Add Constants**: Define `BULK_DISCOUNT_THRESHOLD` (2000.0) and `BULK_DISCOUNT_RATE` (0.05).
2.  **Modify `price_order`**:
    *   Calculate the initial `net` total based on line items.
    *   Check if the order qualifies for the bulk discount: `net > BULK_DISCOUNT_THRESHOLD` AND `not contract`.
    *   If it qualifies, apply the discount to the `net` total.
    *   Proceed with delivery, VAT, and gross calculations using the potentially discounted `net`.

No changes are needed for `storage.py` or `cli.py` as the logic is contained within the pricing module.

```python
# file: pricing.py
"""Prices an order of building materials. Pure logic: no files, no printing, no command line (see storage.py and cli.py)."""

VAT_RATE = 0.19
FREE_DELIVERY_FROM = 500.0        # net goods value at or above which delivery is free (FIX 2: was "over", so exactly 500 paid)
DELIVERY_FEE = 45.0
CONTRACT_DISCOUNT = 0.08          # contract customers pay 92% of list price
BULK_DISCOUNT_THRESHOLD = 2000.0  # orders over this net value get a bulk discount
BULK_DISCOUNT_RATE = 0.05         # 5% discount for qualifying bulk orders


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
                "lines": lines, "net": None, "delivery": None, "vat": None, "gross": None}
    
    net = round(sum(l["total"] for l in lines), 2)
    
    # Apply 5% discount for orders over 2,000 EUR, but not for contract rates
    if net > BULK_DISCOUNT_THRESHOLD and not contract:
        net = round(net * (1 - BULK_DISCOUNT_RATE), 2)

    fee = delivery_fee(net)
    vat = round((net + fee) * VAT_RATE, 2)
    return {"order": order["id"], "status": "ok", "errors": [], "lines": lines,
            "net": net, "delivery": fee, "vat": vat, "gross": round(net + fee + vat, 2)}
```

---
44.1s, files changed: ['pricing.py']

PASS 2480 gets discount 2803.64 2803.64
PASS contract gets none 2715.1 2715.1
PASS exactly 2000: none 2380.0 2380.0
PASS 2000.01: discount 2261.01 2261.01
PASS 1990 net (gross>2000): none 2368.1 2368.1
PASS small order unchanged 172.55 172.55
FAIL CLI shows the discount: Order L: net 2356.00  delivery 0.00  VAT 447.64  total 2803.64
