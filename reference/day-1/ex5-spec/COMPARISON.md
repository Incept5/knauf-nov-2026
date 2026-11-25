# Plain prompt against specification: a real run (25 Nov 2026)

Model: Qwen3.8-27B (MLX 4-bit, thinking off). Same code (`base/`: bugs fixed, no discount). 3 runs each (temperature 0, 0.7, 0.7).
Plain prompt = the one sentence from Exercise 2. Spec = `SPEC.md`. Replies in `runs/`; re-score with `python3 compare_prompts.py --label mlx-27b --rescore`.

| | plain sentence | specification |
|---|---|---|
| Amount payable correct (6 cases incl. boundaries, contract) | 3 / 3 runs | 3 / 3 runs |
| Discount visible on the command line | **1 / 3** (2 runs changed only `pricing.py`) | 3 / 3 |
| Passes the spec's 7 acceptance tests | 0 / 3 (1/7, 1/7, 6/7) * | 3 / 3 (7/7) |
| Time per reply | 44 to 59 s | 58 to 77 s |

\* Mostly because the plain runs were never told the result needs a `discount` field, so judge them on the first two rows.

**What to say:** on a 60-line program the model guessed the money right both times ("net", "strictly over"). What the plain prompt got wrong was
what nobody asked for: in 2 of 3 runs the customer's total silently dropped by 5% with no line saying why. The spec's value is that these choices
are written down, decided by the business and testable, not that the model is cleverer. Do not promise attendees a dramatic failure.

**Also seen:** 4 of 6 replies ignored the requested code-fence format. Our first scorer applied nothing and reported false failures: check your checker.
