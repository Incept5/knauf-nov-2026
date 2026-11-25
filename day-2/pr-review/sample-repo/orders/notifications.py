"""Order confirmations. Log ids only, never names or email addresses (standard 6)."""
import logging

log = logging.getLogger(__name__)


def build_confirmation(order_id: str, gross: str) -> str:
    return f"Thank you. Your order {order_id} (total {gross} EUR incl. VAT) has been received."


def send_confirmation(order_id: str, customer_id: int, gross: str) -> None:
    message = build_confirmation(order_id, gross)
    _send_mail(customer_id, message)
    log.info("confirmation sent order=%s customer=%s", order_id, customer_id)


def _send_mail(customer_id: int, message: str) -> None:
    """Stub: the real mail provider is not wired up in this sample."""
