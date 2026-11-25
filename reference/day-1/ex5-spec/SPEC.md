# Specification: 5% volume discount on large orders

**Goal** (one sentence, the outcome, not the implementation):
Customers without a contract rate pay 5% less for the goods on any order whose goods value is over 2,000.00 EUR net, and can see that on the priced order.

**Users and context** (who uses it, when, what they already have):
Sales office staff price orders with `python3 cli.py [orders.json]`. Products are in `data/products.json`, orders in `data/orders.json`. Contract customers already get 8% off every line.

**Requirements** (numbered, testable, one thing each):
1. "Goods value" is the sum of the line totals (list prices, rounded per line), excluding delivery and VAT.
2. If an order is not a contract order and its goods value is strictly greater than 2,000.00 EUR, the discount is 5% of the goods value, rounded to cents.
3. Contract orders never get this discount, whatever their value (the contract rate stays as it is).
4. An order of exactly 2,000.00 EUR gets no discount.
5. `net` = goods value minus discount. Delivery is decided on `net` (free from 500.00), and VAT (19%) is charged on `net` plus delivery.
6. The result of `price_order` has a `discount` key (0.0 when none). `net` is after the discount; `goods` is before it.
7. The command line shows `discount -124.00` on a discounted order and nothing extra on other orders.
8. Both thresholds and rates are named constants at the top of `pricing.py`.

**Constraints** (tech, data, standards, performance, what must not change):
Python 3 standard library only. `pricing.py` stays free of file and printing code. Prices of orders that get no discount must not change by a cent.
An order with an unknown SKU is still reported as not priced. Do not change the data files' format.

**Out of scope:**
Discount tiers, per-customer thresholds, combining several orders, invoices, currency other than EUR, changing the contract rate.

**Acceptance tests** (given / when / then):
- Given a non-contract order of 200 x PB-150 (2,480.00), when priced, then discount 124.00, net 2,356.00, delivery 0.00, gross 2,803.64.
- Given the same order with the contract rate, when priced, then discount 0.00, net 2,281.60, gross 2,715.10.
- Given a non-contract order with goods of exactly 2,000.00, when priced, then discount 0.00 and gross 2,380.00.
- Given goods of 2,000.01, when priced, then discount 100.00 and net 1,900.01, gross 2,261.01.
- Given goods of 1,990.00 (gross 2,368.10), when priced, then no discount.
- Given the shipped orders A-1001 to A-1004, when run, then output is unchanged.

**Open questions** (ask the AI to list the gaps it finds, then answer them here):
| Question an AI (or a good colleague) should raise | Answer (decided for the workshop; the "business owner" must confirm) |
|---|---|
| Is 2,000 EUR net or gross (with VAT)? | Net goods value. |
| Is delivery included in the 2,000? | No. |
| Exactly 2,000.00: discount or not? | No. "Over" means strictly greater. |
| Before or after VAT is the discount applied? | Before VAT. |
| Is delivery free decided before or after the discount? | After (on `net`). With these numbers it cannot change the result, but write it down. |
| Does the discount apply to delivery? | No, goods only. |
| Does "contract rate" mean the order's `contract` flag? | Yes. |
| Round per line or on the total? | Lines as today; the discount once on the goods total. |
| Should the invoice show it separately? | Yes, a `discount` field and on the command line. |
| What about orders with an unknown SKU? | Not priced at all, as today. |

**Context for the agent** (files to read, coding standards, links):
`pricing.py` (rules), `storage.py` (file reading), `cli.py` (output), `data/*.json`. Keep the style. Plan first, then implement, then write `unittest` tests that map one-to-one to the acceptance tests, then run them.
