# Coding standards (order-service)

Reviewers (human or AI) check changes against these rules. Each rule has a number so a comment can cite it.

1. **Naming.** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for constants.
   Use full words in new code (`customer`, not `cust`). Old abbreviations in `reports.py` are being cleaned up.
2. **Money is `Decimal`, never `float`.** Build it from strings (`Decimal("19.99")`), round to cents with
   `ROUND_HALF_UP` once per line total, and send it to other systems as a string.
3. **Validate input at the edge.** Anything from outside (requests, files) is checked in `api.py`:
   quantity is a whole number above zero, SKU matches `[A-Z]{3}-[0-9]{4}`. Reject bad input; do not "fix" it.
4. **SQL uses parameters.** Never build a query with `+`, `%` or an f-string.
5. **No secrets in code.** Keys, passwords and tokens come from environment variables through `config.py`.
6. **Logging carries no personal data.** Log ids (order, customer) only. Never log a name, email, address or phone number.
7. **Specific errors.** Raise the exceptions from `errors.py`. No bare `except:`, and never swallow an error silently.
8. **Boundaries are written down and tested.** If a rule says "over 500" or "100 or more", the docstring says
   whether the limit itself is included, and a test checks the limit and the values on either side.
9. **Tests for money, payments and auth.** A change to `pricing`, `payments` or `auth` comes with tests.
10. **Small functions, typed signatures.** Public functions have type hints and stay under about 40 lines.
11. **One purpose per pull request.** Keep mechanical changes (renames, formatting) apart from behaviour
    changes. Aim for under 300 changed lines.
12. **Time zones.** Use timezone-aware datetimes and store UTC.
13. **Standard library first.** A new third-party dependency needs approval from the team lead.
14. **Say the unit.** Docstrings and names state currency (EUR) and units (m2, kg, pieces) where it is not obvious.
