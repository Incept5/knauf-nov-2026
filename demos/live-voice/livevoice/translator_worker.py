"""Translator worker process: JSON lines in on stdin, JSON lines out on stdout.

Runs in its own process so a translation never stalls the live Parakeet decodes
(MLX is single-threaded per process; a separate process gets its own GPU queue).

in : {"id": 3, "text": "Let's paint the screen blue."}
out: {"id": 3, "delta": "Lassen"} ... then {"id": 3, "done": true, "text": "...", "ms": 412, "first_ms": 95}
"""

from __future__ import annotations

import json
import os
import sys
import time

MODEL_ID = os.environ.get("LIVEVOICE_TRANSLATE_MODEL", "mlx-community/Qwen3.5-4B-MLX-4bit")

SYSTEM = (
    "You are a live interpreter at a tech conference in Berlin. Translate the user's {src} text "
    "into natural, fluent {tgt}. Keep names, product names and technical terms as they are. "
    "Output only the {tgt} translation: no quotes, no notes, no preamble."
)

# Parakeet v3 is multilingual and the speaker may switch to German. A 4B model told
# "if it's already German, translate to English" just echoes the German, so detect the
# language here and give it an explicit direction instead.
_DE = set("der die das und ist nicht ich wir ihr sie es ein eine einen dem den des zu mit auf "
          "für von im ist sind war haben hat auch noch jetzt heute hier bitte danke schön "
          "machen wie was wo warum aber oder wenn dann nur sehr gut".split())
_EN = set("the and is are not i we you it a an to of with on for from in was have has also "
          "now today here please thank make how what where why but or if then only very good".split())


def is_german(text: str) -> bool:
    words = [w.strip(".,!?;:\"'").lower() for w in text.split()]
    de = sum(w in _DE for w in words) + 2 * sum(any(c in w for c in "äöüß") for w in words)
    en = sum(w in _EN for w in words)
    return de > en


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    from mlx_lm import load, stream_generate

    model, tok = load(MODEL_ID)

    def prompt(text, de=False):
        src, tgt = ("German", "English") if de else ("English", "German")
        return tok.apply_chat_template(
            [{"role": "system", "content": SYSTEM.format(src=src, tgt=tgt)}, {"role": "user", "content": text}],
            add_generation_prompt=True, tokenize=False, enable_thinking=False,
        )

    for _ in stream_generate(model, tok, prompt("Hello."), max_tokens=8):  # warm-up
        pass
    emit({"ready": True, "model": MODEL_ID})

    for line in sys.stdin:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        t0 = time.perf_counter()
        first = None
        text = ""
        de = is_german(req["text"])
        target = "en" if de else "de"
        for r in stream_generate(model, tok, prompt(req["text"], de), max_tokens=200):
            if r.text:
                if first is None:
                    first = (time.perf_counter() - t0) * 1000
                text += r.text
                emit({"id": req["id"], "delta": r.text, "target": target})
        emit({"id": req["id"], "done": True, "text": text.strip(), "target": target,
              "ms": round((time.perf_counter() - t0) * 1000), "first_ms": round(first or 0)})


if __name__ == "__main__":
    main()
