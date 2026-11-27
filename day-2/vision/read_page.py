"""Ask a vision model a question about ONE page image (standard library only).

  python3 read_page.py 16                       # default question for page 16, default backend
  python3 read_page.py 16 --backend astra
  python3 read_page.py 16 --backend local       # needs a local vision model (see README.md)
  python3 read_page.py 12 --question "Which city has the highest purchasing power, and which the lowest?"
  python3 read_page.py path/to/any-page.png --question "What does this chart show?"

Pages 12, 15 and 16 of the Munich economic report go in ../data/pages/ (muenchen-p12.png ...); see ../data/SOURCES.md.
The model gets the page as an IMAGE, so it reads the chart itself instead of a text layer that can garble digits.

Backends (see ../common/llm.py): `cluster` is Incept5's Spark cluster (OpenAI chat-completions format), `astra` is
GPT-6 Astra (OpenAI Responses format). The two use different image formats, handled here. `local` is a model on your machine.
Tested live with local vision models and, on 25 Nov 2026, through the cluster with qwen3.6-35b and deepseek-v4.1-flash
(on page 15 deepseek misread two numbers: check them). qwen3.8-27b can read images, but the cluster engine serving it does not support them yet. Astra has not been tested live.
"""
import argparse, base64, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from llm import chat, default_backend, BACKENDS   # noqa: E402

DEFAULTS = {
    "16": "In which year was the number of employees affected by insolvencies (betroffene Arbeitnehmer*innen) highest? Give the year and the number, and say which other year was closest.",
    "12": "Which city has the highest purchasing power per inhabitant in 2025, and which has the lowest? Give the values.",
    "15": "How many business registrations and deregistrations were there in 2025, and how do they compare with 2024?",
}


def build_messages(backend, question, png_bytes):
    """One user message with text + image, in the wire format that backend expects."""
    url = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
    if BACKENDS[backend]["api"] == "responses":
        content = [{"type": "input_text", "text": question}, {"type": "input_image", "image_url": url}]
    else:
        content = [{"type": "text", "text": question}, {"type": "image_url", "image_url": {"url": url}}]
    return [{"role": "user", "content": content}]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page", help="page number 12, 15 or 16, or a path to a PNG/JPEG")
    ap.add_argument("--question", help="your question (default depends on the page)")
    ap.add_argument("--backend", choices=list(BACKENDS), default=None)
    ap.add_argument("--max-tokens", type=int, default=3000, help="reply limit; models that think first need the room (default 3000)")
    a = ap.parse_args()
    path = a.page if os.path.exists(a.page) else os.path.join(HERE, "..", "data", "pages", f"muenchen-p{a.page}.png")
    if not os.path.exists(path):
        sys.exit(f"No image at {path}. Run git pull to get the page images, or pass a PNG path.")
    question = a.question or DEFAULTS.get(a.page, "Describe this page: what does each chart show, and what are the key numbers?")
    backend = a.backend or default_backend()
    with open(path, "rb") as f:
        png = f.read()
    print(f"[{backend}] {os.path.basename(path)} ({len(png) // 1024} KB)\nQ: {question}\n")
    t = time.time()
    answer = chat("", backend=backend, messages=build_messages(backend, question, png), max_tokens=a.max_tokens)
    print(answer or "(empty reply: the model may have used its whole token budget thinking)")
    print(f"\n[{time.time() - t:.1f}s]  Check the answer against the page image yourself.")


if __name__ == "__main__":
    main()
