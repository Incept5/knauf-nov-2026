"""Prices an order of building materials."""
import json

VAT_RATE = 0.19
FREE_DELIVERY_OVER = 500.0
DELIVERY_FEE = 45.0
CONTRACT_DISCOUNT = 0.08


def load_products(path):
    with open(path) as f:
        return {p["sku"]: p for p in json.load(f)}


def line_total(product, quantity, contract):
    price = product["unit_price"]
    if contract:
        price = price * CONTRACT_DISCOUNT
    return round(price * quantity, 2)


def delivery_fee(net_total):
    if net_total > FREE_DELIVERY_OVER:
        return 0.0
    return DELIVERY_FEE


def price_order(order, products):
    net = 0.0
    lines = []
    for item in order["items"]:
        product = products[item["sku"]]
        total = line_total(product, item["qty"], order.get("contract", False))
        lines.append({"sku": item["sku"], "name": product["name"], "qty": item["qty"], "total": total})
        net += total
    fee = delivery_fee(net)
    vat = round((net + fee) * VAT_RATE, 2)
    return {"order": order["id"], "lines": lines, "net": round(net, 2), "delivery": fee,
            "vat": vat, "gross": round(net + fee + vat, 2)}
