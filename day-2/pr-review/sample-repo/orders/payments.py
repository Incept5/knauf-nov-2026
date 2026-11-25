"""Charges through the payment gateway (fictional). The key comes from config (standard 5)."""
import json
import logging
import urllib.error
import urllib.request
from decimal import Decimal

from orders import config
from orders.errors import PaymentError

log = logging.getLogger(__name__)


def _post(path: str, body: dict) -> dict:
    request = urllib.request.Request(
        config.PAYMENT_BASE_URL + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + config.PAYMENT_API_KEY},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:
            return json.load(reply)
    except urllib.error.URLError as error:
        raise PaymentError(f"gateway unreachable: {error.reason}") from error


def charge(order_id: str, amount: Decimal) -> str:
    """Charge the full gross amount in EUR. Returns the gateway payment id."""
    reply = _post("/charges", {"order_id": order_id, "amount": str(amount), "currency": "EUR"})
    log.info("charged order=%s", order_id)
    return reply["payment_id"]
