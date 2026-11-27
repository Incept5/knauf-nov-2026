#!/usr/bin/env python3
"""GDPR articles (English) as structured JSON. Standard library only. The German twin is scrape_gdpr_article-de.py.

    export INCEPT5_API_KEY=...
    python3 scrape_gdpr_article.py                 # Art. 17 and Art. 22
    python3 scrape_gdpr_article.py 15 16 17        # the articles you name
    python3 scrape_gdpr_article.py --all           # all 99 articles (one model call each)
    python3 scrape_gdpr_article.py --live          # fetch the pages again instead of using the saved text

The code copies the title and the full text from the page; the model only writes the summary. So the law itself cannot be
changed or invented by the model. Check the summary against the text. Source: https://gdpr-info.eu (Regulation (EU) 2016/679).
"""
import argparse, json, pathlib, re, sys, urllib.request
from html.parser import HTMLParser

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
sys.dont_write_bytecode = True
from llm import chat  # noqa: E402

URL = "https://gdpr-info.eu/art-{}-gdpr/"
SAVED = HERE / "gdpr"                 # one small JSON file per article, so a rerun needs no internet
SYSTEM = ("You are a careful data-protection assistant. Summarise the article in at most two sentences of plain English. "
          "Only what the text says, no interpretation. Reply with the summary only.")


class ArticlePage(HTMLParser):
    """Pull the title and the numbered paragraphs out of one article page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.lines = "", []
        self._depth = 0          # <div> depth inside the article body
        self._in_title = False
        self._lists = []         # [kind, counter] per open <ol>/<ul>
        self._text = []

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._text)).strip()
        if text:
            self.lines.append(text)
        self._text = []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if tag == "span" and "dsgvo-title" in cls:
            self._in_title = True
        if tag == "div" and (self._depth or "entry-content" in cls.split()):
            self._depth += 1
        if not self._depth:
            return
        if tag in ("ol", "ul"):
            self._flush()
            self._lists.append([tag, 0])
        elif tag == "li" and self._lists:
            self._flush()
            kind, level = self._lists[-1], len(self._lists)
            kind[1] += 1
            # top level: 1. 2. 3.   second level: a) b) c)   third: i, ii ...
            mark = f"{kind[1]}." if level == 1 else f"{chr(96 + kind[1])})" if level == 2 else "–"
            self._text.append("  " * (level - 1) + mark + " ")
            self.lines.append(f"\x00{level}")
        elif tag in ("p", "br"):
            self._flush()

    def handle_endtag(self, tag):
        if tag == "span":
            self._in_title = False
        if not self._depth:
            return
        if tag in ("li", "p"):
            self._flush()
        elif tag in ("ol", "ul") and self._lists:
            self._flush()
            self._lists.pop()
        elif tag == "div":
            self._flush()
            self._depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._depth:
            self._text.append(re.sub(r"^\d+(?=[A-ZÄÖÜ„])", "", data))   # sentence numbers glued to the first word

    def article_text(self):
        out, level = [], 1
        for line in self.lines:
            if line.startswith("\x00"):
                level = int(line[1:])
                continue
            m = re.match(r"^(\d+\.|[a-z]\)|–) ?(.*)$", line)
            out.append("   " * (level - 1) + f"{m[1]} {m[2]}" if m else line)
        for i, line in enumerate(out):                       # the site's own links follow the law text: cut them off
            if line.lstrip().startswith(("Suitable Recitals", "←", "→", "GDPR Table of Contents", "GDPR Table of contents", "Report error")) or line.endswith("GDPR→"):
                out = out[:i]
                break
        return "\n".join(out).strip()


def fetch(number, live=False):
    """{"article", "title", "full_article"} for one article, from the saved copy unless live."""
    saved = SAVED / f"art-{number}.json"
    if saved.exists() and not live:
        return json.loads(saved.read_text(encoding="utf-8"))
    request = urllib.request.Request(URL.format(number), headers={"User-Agent": "Mozilla/5.0 (workshop example)"})
    try:
        with urllib.request.urlopen(request, timeout=30) as reply:
            html = reply.read().decode("utf-8", errors="replace")
    except OSError as e:
        raise SystemExit(f"Cannot fetch {URL.format(number)} ({e}). Is the network or Zscaler blocking it? "
                         f"Art. 17 and 22 are saved in {SAVED.name}/.")
    page = ArticlePage()
    page.feed(html)
    text = page.article_text()
    if not page.title or len(text) < 40:
        raise SystemExit(f"Art. {number}: the page layout was not recognised")
    article = {"article": f"Art. {number}", "title": page.title.strip(), "full_article": text}
    SAVED.mkdir(exist_ok=True)
    saved.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return article


def main():
    ap = argparse.ArgumentParser(description="GDPR articles as JSON with a summary")
    ap.add_argument("articles", nargs="*", type=int, default=[17, 22])
    ap.add_argument("--all", action="store_true", help="all 99 articles")
    ap.add_argument("--backend", default=None, help="cluster (default) or astra")
    ap.add_argument("--live", action="store_true", help="fetch the pages even if a saved copy exists")
    ap.add_argument("--out", default="gdpr_articles.json")
    a = ap.parse_args()

    result = {"regulation": "GDPR", "articles": []}
    for number in (range(1, 100) if a.all else a.articles):
        if not 1 <= number <= 99:
            raise SystemExit(f"The GDPR has articles 1 to 99, not {number}")
        article = fetch(number, a.live)
        print(f"{article['article']}: {article['title']} ({len(article['full_article']):,} characters)", file=sys.stderr)
        summary = chat(f"{article['article']} GDPR, {article['title']}\n\n{article['full_article']}",
                       system=SYSTEM, backend=a.backend, max_tokens=600)
        result["articles"].append({"article": article["article"], "title": article["title"],
                                   "summary": summary, "full_article": article["full_article"]})

    text = json.dumps(result, ensure_ascii=False, indent=2)
    pathlib.Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nSaved {len(result['articles'])} article(s) to {a.out}. Check each summary against the text.", file=sys.stderr)


if __name__ == "__main__":
    main()
