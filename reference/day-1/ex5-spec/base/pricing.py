"""Prices an order of building materials. Pure logic: no files, no printing, no command line (see storage.py and cli.py)."""

VAT_RATE = 0.19
FREE_DELIVERY_FROM = 500.0        # net goods value at or above which delivery is free (FIX 2: was "over", so exactly 500 paid)
DELIVERY_FEE = 45.0
CONTRACT_DISCOUNT = 0.08          # contract customers pay 92% of list price


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
    fee = delivery_fee(net)
    vat = round((net + fee) * VAT_RATE, 2)
    return {"order": order["id"], "status": "ok", "errors": [], "lines": lines,
            "net": net, "delivery": fee, "vat": vat, "gross": round(net + fee + vat, 2)}
