"""Exceptions used across the service (standard 7)."""


class OrderError(Exception):
    """Base class for every error this service raises on purpose."""


class ValidationError(OrderError):
    """The caller sent something we refuse to process."""


class PaymentError(OrderError):
    """The payment gateway refused or could not be reached."""
