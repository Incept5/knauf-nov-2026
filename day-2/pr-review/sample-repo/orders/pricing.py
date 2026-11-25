"""Order pricing. All money is Decimal in EUR (standard 2)."""
from decimal import Decimal, ROUND_HALF_UP

from orders.catalogue import unit_price_for

CENT = Decimal("0.01")
VAT_RATE = Decimal("0.19")
FREE_DELIVERY_OVER = Decimal("500.00")   # net total must be strictly above this
DELIVERY_FEE = Decimal("45.00")
CONTRACT_DISCOUNT = Decimal("0.08")      # 8% off for contract customers


def to_money(value) -> Decimal:
    """Round to whole cents, halves go up."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(unit_price: Decimal, quantity: int, contract: bool) -> Decimal:
    """Net price of one order line in EUR."""
    price = unit_price
    if contract:
        price = price * (Decimal("1") - CONTRACT_DISCOUNT)
    return to_money(price * quantity)


def delivery_fee(net_total: Decimal) -> Decimal:
    """Delivery is free when the net total is strictly above 500.00 EUR (500.00 itself still pays)."""
    if net_total > FREE_DELIVERY_OVER:
        return Decimal("0.00")
    return DELIVERY_FEE


def price_order(items: list, contract: bool = False) -> dict:
    """items is a list of {"sku": str, "quantity": int}. Returns Decimal amounts in EUR."""
    lines = []
    net = Decimal("0.00")
    for item in items:
        total = line_total(unit_price_for(item["sku"]), item["quantity"], contract)
        lines.append({"sku": item["sku"], "quantity": item["quantity"], "total": total})
        net += total
    fee = delivery_fee(net)
    vat = to_money((net + fee) * VAT_RATE)
    return {"lines": lines, "net": net, "delivery": fee, "vat": vat, "gross": net + fee + vat}
