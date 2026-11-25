"""Management reports. Older code: names are abbreviated and still to be cleaned up (standard 1).

Every function takes plain lists of dicts, so it can be run without a database.
Amounts are Decimal strings in EUR.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
OVERDUE_AFTER_DAYS = 30


def fmt_amt(amt):
    """Format an amount in EUR with two decimals, halves round up."""
    return str(Decimal(str(amt)).quantize(CENT, rounding=ROUND_HALF_UP))


def sum_amts(amts):
    tot = Decimal("0.00")
    for amt in amts:
        tot += Decimal(str(amt))
    return tot


def group_by_cust(rows):
    res = defaultdict(list)
    for row in rows:
        res[row["cust_id"]].append(row)
    return res


def group_by_prod(rows):
    res = defaultdict(list)
    for row in rows:
        res[row["prod_sku"]].append(row)
    return res


def daily_sales(rows, day):
    """Sales for one day: order count, units and net amount."""
    cnt = 0
    qty_tot = 0
    amt_tot = Decimal("0.00")
    for row in rows:
        if row["order_dt"] != day:
            continue
        cnt += 1
        qty_tot += row["qty"]
        amt_tot += Decimal(str(row["amt"]))
    return {"day": day, "orders": cnt, "units": qty_tot, "net": fmt_amt(amt_tot)}


def daily_sales_range(rows, first_day, last_day):
    res = []
    days = sorted({row["order_dt"] for row in rows})
    for day in days:
        if first_day <= day <= last_day:
            res.append(daily_sales(rows, day))
    return res


def cust_statement(rows, cust_id):
    """All orders of one customer with a running total."""
    lst = [row for row in rows if row["cust_id"] == cust_id]
    lst.sort(key=lambda row: row["order_dt"])
    run_tot = Decimal("0.00")
    out = []
    for row in lst:
        run_tot += Decimal(str(row["amt"]))
        out.append({
            "order_id": row["order_id"],
            "order_dt": row["order_dt"],
            "amt": fmt_amt(row["amt"]),
            "run_tot": fmt_amt(run_tot),
        })
    return out


def cust_totals(rows):
    res = {}
    for cust_id, cust_rows in group_by_cust(rows).items():
        res[cust_id] = {
            "orders": len(cust_rows),
            "units": sum(row["qty"] for row in cust_rows),
            "amt": fmt_amt(sum_amts(row["amt"] for row in cust_rows)),
        }
    return res


def top_custs(rows, limit=5):
    tots = cust_totals(rows)
    ranked = sorted(tots.items(), key=lambda pair: Decimal(pair[1]["amt"]), reverse=True)
    return [{"cust_id": cust_id, **tot} for cust_id, tot in ranked[:limit]]


def prod_totals(rows):
    res = {}
    for sku, prod_rows in group_by_prod(rows).items():
        res[sku] = {
            "units": sum(row["qty"] for row in prod_rows),
            "amt": fmt_amt(sum_amts(row["amt"] for row in prod_rows)),
            "orders": len({row["order_id"] for row in prod_rows}),
        }
    return res


def top_prods(rows, limit=5):
    tots = prod_totals(rows)
    ranked = sorted(tots.items(), key=lambda pair: pair[1]["units"], reverse=True)
    return [{"prod_sku": sku, **tot} for sku, tot in ranked[:limit]]


def slow_prods(rows, all_skus, min_qty=1):
    """SKUs that sold fewer than min_qty units in the period."""
    sold = defaultdict(int)
    for row in rows:
        sold[row["prod_sku"]] += row["qty"]
    return sorted(sku for sku in all_skus if sold[sku] < min_qty)


def vat_summary(rows, vat_rate=Decimal("0.19")):
    """Net, VAT and gross for the period. VAT is rounded once on the total."""
    net_tot = sum_amts(row["amt"] for row in rows)
    vat_tot = (net_tot * vat_rate)
    return {
        "net": fmt_amt(net_tot),
        "vat": fmt_amt(vat_tot),
        "gross": fmt_amt(net_tot + Decimal(fmt_amt(vat_tot))),
    }


def overdue_invs(invs, today):
    """Invoices unpaid for more than 30 days (day 30 itself is not overdue)."""
    res = []
    for inv in invs:
        if inv["paid"]:
            continue
        age_days = (today - inv["inv_dt"]).days
        if age_days > OVERDUE_AFTER_DAYS:
            res.append({"inv_id": inv["inv_id"], "cust_id": inv["cust_id"], "age_days": age_days,
                        "amt": fmt_amt(inv["amt"])})
    res.sort(key=lambda row: row["age_days"], reverse=True)
    return res


def overdue_by_cust(invs, today):
    res = defaultdict(lambda: Decimal("0.00"))
    for inv in overdue_invs(invs, today):
        res[inv["cust_id"]] += Decimal(inv["amt"])
    return {cust_id: fmt_amt(amt) for cust_id, amt in res.items()}


def avg_order_amt(rows):
    ids = {row["order_id"] for row in rows}
    if not ids:
        return fmt_amt(0)
    return fmt_amt(sum_amts(row["amt"] for row in rows) / len(ids))


def avg_units_per_order(rows):
    ids = {row["order_id"] for row in rows}
    if not ids:
        return 0
    return sum(row["qty"] for row in rows) / len(ids)


def delivery_summary(rows):
    """Count of orders that paid delivery vs got it free."""
    paid_cnt = 0
    free_cnt = 0
    for row in rows:
        if Decimal(str(row["delivery_amt"])) > 0:
            paid_cnt += 1
        else:
            free_cnt += 1
    return {"paid": paid_cnt, "free": free_cnt}


def delivery_amt_tot(rows):
    return fmt_amt(sum_amts(row["delivery_amt"] for row in rows))


def contract_vs_list(rows):
    """Compare contract and list-price customers."""
    contract_rows = [row for row in rows if row["contract"]]
    list_rows = [row for row in rows if not row["contract"]]
    return {
        "contract_orders": len({row["order_id"] for row in contract_rows}),
        "list_orders": len({row["order_id"] for row in list_rows}),
        "contract_amt": fmt_amt(sum_amts(row["amt"] for row in contract_rows)),
        "list_amt": fmt_amt(sum_amts(row["amt"] for row in list_rows)),
    }


def month_key(dt):
    return f"{dt.year:04d}-{dt.month:02d}"


def monthly_sales(rows):
    res = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        res[month_key(row["order_dt"])] += Decimal(str(row["amt"]))
    return {key: fmt_amt(amt) for key, amt in sorted(res.items())}


def monthly_growth(rows):
    """Percentage change of net sales from one month to the next."""
    sales = monthly_sales(rows)
    keys = sorted(sales)
    res = []
    for prev_key, key in zip(keys, keys[1:]):
        prev_amt = Decimal(sales[prev_key])
        amt = Decimal(sales[key])
        if prev_amt == 0:
            pct = None
        else:
            pct = ((amt - prev_amt) / prev_amt * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        res.append({"month": key, "net": sales[key], "growth_pct": pct})
    return res


def csv_line(vals):
    return ";".join(str(val) for val in vals)


def cust_statement_csv(rows, cust_id):
    lines = [csv_line(["order_id", "order_dt", "amt", "run_tot"])]
    for entry in cust_statement(rows, cust_id):
        lines.append(csv_line([entry["order_id"], entry["order_dt"], entry["amt"], entry["run_tot"]]))
    return "\n".join(lines)


def top_custs_text(rows, limit=5):
    lines = []
    for pos, entry in enumerate(top_custs(rows, limit), start=1):
        lines.append(f"{pos}. customer {entry['cust_id']}: {entry['orders']} orders, "
                     f"{entry['units']} units, {entry['amt']} EUR")
    return "\n".join(lines)


def top_prods_text(rows, limit=5):
    lines = []
    for pos, entry in enumerate(top_prods(rows, limit), start=1):
        lines.append(f"{pos}. {entry['prod_sku']}: {entry['units']} units in "
                     f"{entry['orders']} orders, {entry['amt']} EUR")
    return "\n".join(lines)


def overdue_text(invs, today):
    lines = []
    for inv in overdue_invs(invs, today):
        lines.append(f"invoice {inv['inv_id']} (customer {inv['cust_id']}): "
                     f"{inv['amt']} EUR, {inv['age_days']} days old")
    return "\n".join(lines) or "nothing overdue"
