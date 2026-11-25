Here are the bugs I am confident about, ordered by severity:

1.  **Critical:** `cli.py` ignores the `path` argument and hardcodes `"data/products.json"` in `load_products`, so it cannot load products from a different location than orders.
2.  **High:** `pricing.py` `line_total` applies the contract discount by multiplying the unit price by the discount rate (0.08), resulting in a 92% price reduction instead of the intended 8% discount.
3.  **Medium:** `pricing.py` `price_order` raises a `KeyError` and crashes if an order contains an SKU that does not exist in the `products` dictionary (as seen with "XX-999" in `data/orders.json`).
4.  **Low:** `pricing.py` `delivery_fee` uses a strict greater-than comparison (`>`), so an order totaling exactly 500.00 is charged the delivery fee, whereas "free over 500" typically implies >= 500.00 is free.

---
15.8s
