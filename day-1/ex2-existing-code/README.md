# Exercise 2: understand and extend existing code (25 min)

`order_pricing/` is a small command-line tool that prices building-materials orders. It has **no tests** and **three
bugs we have not told you about** (one in the maths, one in a boundary, one in the data handling).

**Do not read the code first. Ask the AI.**
1. "Explain what this project does and how it is laid out." Check the answer against the code.
2. "Write tests for it." Run them. Which tests fail, and is the test or the code wrong?
3. Find and fix the bugs. How did you decide the AI was right?
4. Add a feature: **a 5% discount for orders over 2,000 EUR, but not for orders that already have the contract rate.**
5. Refactor: separate pricing from the command-line handling.

Run: `cd order_pricing && python3 cli.py data/orders.json`
Compare approaches with the team next to you: who asked what, and who found the most bugs?
