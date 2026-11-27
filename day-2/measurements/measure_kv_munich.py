"""Measure the Day 2 KV-cache-from-SSD claim on the Munich report: prefill once, save the cache, reload and ask.

  python3 measure_kv_munich.py <pdf> <cache-dir>

Qwen3.6-35B-A3B 4-bit (MLX) on this Mac: prefill the PDF's text once, save the KV-cache to disk,
then reload it and time a question to its first token, as kv-cache/query.py does.
"""
import os, sys, time
from pathlib import Path
import fitz
import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.models.cache import make_prompt_cache, save_prompt_cache, load_prompt_cache

MODEL = os.path.expanduser(os.environ.get("MLX_MODEL", "~/.lmstudio/models/Qwen/Qwen3.6-35B-A3B-4bit"))


def doc_prefix(text):
    """The document alone goes into the cache, under a neutral system message."""
    return ("<|im_start|>system\nThe full text of a report is provided below. Use it to answer the user's questions "
            f"about it.\n\n{text}<|im_end|>\n")


def question_turn(question, noun):
    """One question, appended after the cached document, with thinking switched off."""
    return (f"<|im_start|>user\nAnswer using only the {noun} above; say so if it does not say.\n\n{question}<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n\n</think>\n\n")

pdf, out_dir = sys.argv[1], Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)
text = "\n".join(p.get_text() for p in fitz.open(pdf))
greedy = lambda l: mx.argmax(l, axis=-1)

t0 = time.time(); model, tok = load(MODEL); print(f"model load {time.time()-t0:.1f}s", flush=True)
ids = tok.encode(doc_prefix(text), add_special_tokens=False)
print(f"document prefix: {len(ids):,} tokens", flush=True)

cache = make_prompt_cache(model)
t0 = time.time()
for _ in stream_generate(model, tok, prompt=ids, max_tokens=1, prompt_cache=cache, sampler=greedy):
    pass
dt = time.time() - t0
print(f"prefill {dt:.1f}s ({len(ids)/dt:.0f} tok/s)", flush=True)

path = out_dir / "muenchen-wirtschaftsbericht.safetensors"
save_prompt_cache(str(path), cache)
print(f"cache on disk {path.stat().st_size/1e6:.0f} MB", flush=True)
del cache

for q in ["How many employees subject to social insurance did Munich have in 2025, and how much did that grow?",
          "What was Munich's Gewerbesteuer revenue in 2025, and what was the unemployment rate?"]:
    t0 = time.time()
    base = load_prompt_cache(str(path)); mx.eval([c.state for c in base])
    t_load = time.time() - t0
    first, parts = None, []
    for r in stream_generate(model, tok, prompt=mx.array(tok.encode(question_turn(q, "report"), add_special_tokens=False)),
                             max_tokens=120, prompt_cache=base, sampler=greedy):
        if first is None:
            first = time.time() - t0
        parts.append(r.text)
    print(f"\nQ: {q}\n  cache load {t_load:.2f}s, first token {first:.2f}s after starting the load"
          f"\n  A: {''.join(parts).strip()[:300]}", flush=True)
