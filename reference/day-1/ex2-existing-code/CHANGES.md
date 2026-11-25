# Exercise 2 reference solution: what changed

| # | Bug (original) | Symptom | Fix |
|---|---|---|---|
| 1 maths | `price * CONTRACT_DISCOUNT` (0.08) | contract customer pays 8% of list price: A-1002 shows 49.25 net instead of 566.35 | `price * (1 - 0.08)` |
| 2 boundary | free delivery only if `net > 500` | an order of exactly 500.00 pays 45.00 | `>=` (confirm with the "business": is it "from" or "over" 500?) |
| 3 data | `products[item["sku"]]` | `KeyError: 'XX-999'` kills the whole run at A-1004 | order is reported NOT PRICED with the SKU, run continues, exit code 1 |

**Feature:** 5% off the goods value when it is strictly over 2,000.00 EUR net and the order is not a contract order. Applied before delivery and VAT.
**Refactor:** `pricing.py` pure rules, `storage.py` file reading, `cli.py` arguments and printing (runs from any folder).
**Decisions to challenge:** an order with an unknown SKU is not part-priced (billing a partial order is worse than not billing it);
"over 2,000" is strict; the threshold is the goods value before discount and delivery. No shipped order exceeds 2,000, so the discount is only
visible with `data/orders_large.json` or the tests.

Run: `cd order_pricing && python3 -m unittest discover -s tests -v` and `python3 cli.py`.
Against the original (should be 10 failing of 13): `PRICING_DIR=<repo>/day-1/ex2-existing-code/order_pricing python3 -m unittest discover -s tests`.
