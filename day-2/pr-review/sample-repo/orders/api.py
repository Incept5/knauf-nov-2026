"""Request handlers. Input is validated here, once, at the edge (standard 3)."""
import logging
import re

from orders import db
from orders.auth import is_admin
from orders.errors import ValidationError
from orders.pricing import price_order

log = logging.getLogger(__name__)
SKU_PATTERN = re.compile(r"^[A-Z]{3}-[0-9]{4}$")


def validate_items(items) -> list:
    if not isinstance(items, list) or not items:
        raise ValidationError("items must be a non-empty list")
    clean = []
    for item in items:
        sku, quantity = item.get("sku"), item.get("quantity")
        if not isinstance(sku, str) or not SKU_PATTERN.match(sku):
            raise ValidationError(f"bad sku: {sku!r}")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            raise ValidationError(f"quantity must be a whole number above zero: {quantity!r}")
        clean.append({"sku": sku, "quantity": quantity})
    return clean


def create_order(conn, order_id: str, customer_id: int, payload: dict) -> dict:
    items = validate_items(payload.get("items"))
    priced = price_order(items, contract=bool(payload.get("contract", False)))
    db.save_order(conn, order_id, customer_id, str(priced["gross"]))
    log.info("order created order=%s customer=%s lines=%d", order_id, customer_id, len(items))
    return priced


def get_order(conn, order_id: str, user: dict):
    """Owners see their own orders; admins see all."""
    row = db.get_order(conn, order_id)
    if row is None:
        return None
    if row[1] != user.get("customer_id") and not is_admin(user):
        raise ValidationError("not your order")
    return {"id": row[0], "customer_id": row[1], "gross": row[2]}
