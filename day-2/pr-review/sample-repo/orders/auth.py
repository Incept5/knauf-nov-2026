"""Token check and roles."""
import hmac


def verify_token(supplied: str, expected: str) -> bool:
    """Constant-time comparison. An empty expected token never matches."""
    if not expected:
        return False
    return hmac.compare_digest(supplied.encode(), expected.encode())


def is_admin(user: dict) -> bool:
    return "admin" in user.get("roles", [])
