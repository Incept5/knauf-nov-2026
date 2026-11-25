# Exercise 4: escalate the requirements (10 min). Facilitator notes

Ten minutes is enough to get a PLAN and a first diff, not to finish. Run one round each, or split the three rounds across groups and compare.
Always ask first: "Before you change anything, list what this requirement forces you to change and what you need to ask me."

## Round 1: user roles and login
**Typically breaks:** a password check in browser JavaScript (anyone can read or skip it); plaintext or unsalted passwords; a default "admin/admin";
the UI hides buttons but the server endpoints stay open; no logout or session expiry; the file:// dashboard cannot have real login at all (it needs a server), and the AI may not say so.
**A human must check:** call a protected URL without logging in (curl) and as the wrong role; read how passwords are stored; ask who creates users and resets passwords; should this be Knauf SSO (Entra ID) instead of own accounts?
**Prompt tip:** "Roles: site manager (reads) and planner (edits). Enforce on the server, not in the page. Do not invent your own password storage if a standard exists. Write tests that prove a viewer gets 403."

## Round 2: it must handle 100,000 rows
**Typically breaks (we saw this on our own reference):** the chart code did `Math.min(...allValues)` and crashed with *Maximum call stack size exceeded* at 100,000 rows, while the totals above it still updated, so the page looked half-right.
Also: one SVG element per day; filtering by searching the whole list inside a loop; "add pagination" to a chart; a virtualisation library pulled from a CDN (blocked); a database added when none is needed.
**A human must check:** generate the file and load it (`python3 perf_100k.py`, then the page's file picker); look at the console; time it; check the numbers did not change.
**Prompt tip:** "Here is a 100,000-row file. Measure first, tell me where the time goes, then change only that. No new libraries. Totals must be identical before and after."
**Measured (M5 Max, 3.3 MB CSV):** logic is not the problem: parse+classify ~80 ms (Python and JavaScript), worst weeks 40 to 150 ms. Drawing was: after grouping days into one bucket per half-pixel, a redraw is ~210 ms. Attendee laptops will be slower.

## Round 3: German and English, and explain every change
**Typically breaks:** half-translated UI (tooltips, errors, empty states, chart month names); strings concatenated so German word order is wrong; decimal comma and date format forgotten (12,40 EUR, 25.11.2026) or, worse, applied to the stored data / CSV parsing;
German text overflows buttons on a phone; the explanation describes what the AI *meant* to do, not what it changed.
**A human must check:** switch language and click every control; a German speaker reads it; compare the explanation line by line with `git diff` (any file changed but not explained? any claim with no change behind it?).
**Prompt tip:** "Put all visible strings in one dictionary per language. Format numbers and dates with the browser's Intl for the locale; stored data stays ISO with decimal points. Then list each changed file with one line per change, and say what you did NOT do."

## Debrief question
Which of these three would you have caught by clicking around, and which needed someone who knew what to look for?
