"""Exports for the accounting system. Older code: names are abbreviated (standard 1).

Rows are plain dicts. Amounts are Decimal strings in EUR. Output is semicolon-separated text.
"""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
HEADER = ["inv_id", "cust_id", "inv_dt", "net_amt", "vat_amt", "gross_amt"]


def fmt_amt(amt):
    return str(Decimal(str(amt)).quantize(CENT, rounding=ROUND_HALF_UP))


def esc(val):
    """Quote a text value for the semicolon format."""
    txt = str(val).replace('"', '""')
    if ";" in txt or '"' in txt or "\n" in txt:
        return '"' + txt + '"'
    return txt


def inv_row(inv):
    return [inv["inv_id"], inv["cust_id"], inv["inv_dt"].isoformat(), fmt_amt(inv["net_amt"]),
            fmt_amt(inv["vat_amt"]), fmt_amt(inv["gross_amt"])]


def inv_line(inv):
    return ";".join(esc(val) for val in inv_row(inv))


def export_invs(invs):
    lines = [";".join(HEADER)]
    for inv in invs:
        lines.append(inv_line(inv))
    return "\n".join(lines) + "\n"


def export_invs_for_cust(invs, cust_id):
    return export_invs([inv for inv in invs if inv["cust_id"] == cust_id])


def export_invs_between(invs, first_dt, last_dt):
    sel = [inv for inv in invs if first_dt <= inv["inv_dt"] <= last_dt]
    sel.sort(key=lambda inv: (inv["inv_dt"], inv["inv_id"]))
    return export_invs(sel)


def check_inv(inv):
    """Return a list of problems with one invoice (empty list means fine)."""
    probs = []
    net_amt = Decimal(str(inv["net_amt"]))
    vat_amt = Decimal(str(inv["vat_amt"]))
    gross_amt = Decimal(str(inv["gross_amt"]))
    if net_amt < 0:
        probs.append("negative net amount")
    if vat_amt < 0:
        probs.append("negative VAT amount")
    if net_amt + vat_amt != gross_amt:
        probs.append("net + VAT does not equal gross")
    if not inv["cust_id"]:
        probs.append("missing customer id")
    return probs


def check_invs(invs):
    res = {}
    for inv in invs:
        probs = check_inv(inv)
        if probs:
            res[inv["inv_id"]] = probs
    return res


def split_valid(invs):
    ok_lst = []
    bad_lst = []
    for inv in invs:
        if check_inv(inv):
            bad_lst.append(inv)
        else:
            ok_lst.append(inv)
    return ok_lst, bad_lst


def tot_row(invs):
    net_tot = Decimal("0.00")
    vat_tot = Decimal("0.00")
    gross_tot = Decimal("0.00")
    for inv in invs:
        net_tot += Decimal(str(inv["net_amt"]))
        vat_tot += Decimal(str(inv["vat_amt"]))
        gross_tot += Decimal(str(inv["gross_amt"]))
    return ["TOTAL", "", "", fmt_amt(net_tot), fmt_amt(vat_tot), fmt_amt(gross_tot)]


def export_with_tot(invs):
    txt = export_invs(invs)
    return txt + ";".join(esc(val) for val in tot_row(invs)) + "\n"


def cust_tot_rows(invs):
    by_cust = {}
    for inv in invs:
        cur = by_cust.setdefault(inv["cust_id"], {"cnt": 0, "gross_tot": Decimal("0.00")})
        cur["cnt"] += 1
        cur["gross_tot"] += Decimal(str(inv["gross_amt"]))
    return [[cust_id, cur["cnt"], fmt_amt(cur["gross_tot"])] for cust_id, cur in sorted(by_cust.items())]


def export_cust_tots(invs):
    lines = ["cust_id;inv_cnt;gross_tot"]
    for row in cust_tot_rows(invs):
        lines.append(";".join(esc(val) for val in row))
    return "\n".join(lines) + "\n"


def parse_amt(txt):
    """Read an amount written the German way (1.234,56) or the plain way (1234.56)."""
    txt = txt.strip()
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    return Decimal(txt)


def parse_line(line):
    vals = line.rstrip("\n").split(";")
    if len(vals) != len(HEADER):
        raise ValueError(f"expected {len(HEADER)} fields, got {len(vals)}")
    return {"inv_id": vals[0], "cust_id": vals[1], "inv_dt": vals[2],
            "net_amt": parse_amt(vals[3]), "vat_amt": parse_amt(vals[4]), "gross_amt": parse_amt(vals[5])}


def parse_export(txt):
    lines = txt.splitlines()
    if not lines or lines[0].split(";") != HEADER:
        raise ValueError("unexpected header")
    return [parse_line(line) for line in lines[1:] if line and not line.startswith("TOTAL")]
