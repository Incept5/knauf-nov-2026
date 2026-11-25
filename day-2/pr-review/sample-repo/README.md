# order-service (fictional)

A tiny order service for a fictional building-materials supplier. It prices orders, stores them in SQLite,
takes payment through a (fictional) gateway and sends confirmations. Standard library only.

| File | What it does |
|---|---|
| `orders/catalogue.py` | Product list and unit prices |
| `orders/pricing.py` | Line totals, delivery fee, VAT (all `Decimal`, EUR) |
| `orders/api.py` | Request handlers: validate input, create and fetch orders |
| `orders/db.py` | SQLite access |
| `orders/auth.py` | Token check and roles |
| `orders/payments.py` | Charges through the payment gateway |
| `orders/notifications.py` | Confirmation messages |
| `orders/reports.py` | Older reporting code (abbreviated names, not yet cleaned up) |
| `orders/export.py` | Older accounting export code (same abbreviations) |

Run the tests: `python3 -m unittest discover -s tests -t .`

Read `CODING-STANDARDS.md` before reviewing a change to this code.
