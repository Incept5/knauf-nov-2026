# Vision: ask a model about a page

`read_page.py` sends one page image to a vision model and prints the answer. Standard library only.

```bash
cd day-2/vision
export INCEPT5_API_KEY=...           # and/or ASTRA_KEY=... with LLM_ASTRA_BASE=...
python3 read_page.py 16              # the insolvency chart: which year was highest?
python3 read_page.py 16 --backend astra
python3 read_page.py 12              # purchasing power by city
python3 read_page.py 15              # business registrations 2025 against 2024: check the 2024 numbers carefully
python3 read_page.py 16 --backend local      # a vision model on your own machine
```
A question of your own: `--question "..."`. Longer replies: `--max-tokens` (default 3000). The default backend is `cluster`.

**Get the pages first.** The images are **not in the git repository** (the report is the city's copyright). Ask your facilitator
for `muenchen-p12.png`, `muenchen-p15.png` and `muenchen-p16.png` and put them in `day-2/data/pages/`. Without them, take a
screenshot of the page from the PDF (see `../data/SOURCES.md`) and pass its path: `python3 read_page.py my-page.png --question "..."`.

Pages 12, 15 and 16 of the City of Munich's *Münchner Jahreswirtschaftsbericht 2026* are rendered as images for this exercise.
The report is in German; ask in English and see what comes back.

**Things to try:** the neighbouring-year trap on page 16 (the highest year and the next one are close); compare `cluster`
with `astra`; ask for the underlying data of a chart as a table; ask something only the picture shows.

## Using a local model (checked 25 Nov 2026 on an Apple M5 Max)
- **Use Ollama with `qwen3.5:9b`** (the default `local` model): all page-16, page-12 and page-15 runs were correct, about 4 to 8 s each.
- `qwen3.5:4b` misread the page-16 chart in 5 of 6 runs: too small for this.
- LM Studio models think before answering and cannot be told not to from here: slower, and a small `--max-tokens` can give an
  empty reply.
- **A confident answer can be wrong**, including from larger models: compare every number with the picture.

**Tested live (25 Nov):** the cluster reads these pages with `qwen3.6-35b` and `deepseek-v4.1-flash`. `qwen3.8-27b` and
`inkling-2-mini` do not take images on the cluster yet. Astra has not been tried.
**The pages are the city's copyright** (no licence is stated): they are for use in this workshop and are not meant to be redistributed.
