"""Prices an order of building materials. Pure logic: no files, no printing, no command line (see storage.py and cli.py)."""

VAT_RATE = 0.19
FREE_DELIVERY_FROM = 500.0        # net goods value at or above which delivery is free (FIX 2: was "over", so exactly 500 paid)
DELIVERY_FEE = 45.0
CONTRACT_DISCOUNT = 0.08          # contract customers pay 92% of list price
LARGE_ORDER_OVER = 2000.0         # NEW: orders with goods net strictly over this get the volume discount ...
LARGE_ORDER_DISCOUNT = 0.05       # ... of 5%, unless the order already has the contract rate


def line_total(product, quantity, contract):
    price = product["unit_price"]
    if contract:
        price = price * (1 - CONTRACT_DISCOUNT)   # FIX 1: was price * 0.08, which charged 8% of the price
    return round(price * quantity, 2)


def delivery_fee(net_total):
    return 0.0 if net_total >= FREE_DELIVERY_FROM else DELIVERY_FEE


def volume_discount(goods_net, contract):
    """5% of the goods value for an order over 2,000 EUR net that does not already have the contract rate."""
    if contract or goods_net <= LARGE_ORDER_OVER:
        return 0.0
    return round(goods_net * LARGE_ORDER_DISCOUNT, 2)


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
                "lines": lines, "net": None, "discount": None, "delivery": None, "vat": None, "gross": None}
    goods = round(sum(l["total"] for l in lines), 2)
    discount = volume_discount(goods, contract)
    net = round(goods - discount, 2)
    fee = delivery_fee(net)
    vat = round((net + fee) * VAT_RATE, 2)
    return {"order": order["id"], "status": "ok", "errors": [], "lines": lines, "goods": goods, "discount": discount,
            "net": net, "delivery": fee, "vat": vat, "gross": round(net + fee + vat, 2)}
