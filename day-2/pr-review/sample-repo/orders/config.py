"""Settings come from environment variables (standard 5). Never put a real key in this file."""
import os

DB_PATH = os.environ.get("ORDERS_DB_PATH", "orders.db")
PAYMENT_BASE_URL = os.environ.get("PAYMENT_BASE_URL", "https://payments.example.test/v1")
PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY", "")
API_TOKEN = os.environ.get("ORDERS_API_TOKEN", "")
