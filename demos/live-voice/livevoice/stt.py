"""Streaming wrapper around Parakeet (mlx-audio).

Parakeet-TDT-0.6B-v3 decodes 14 s of audio in ~55 ms on an M5 Max, so the
simplest robust streaming scheme works: keep the uncommitted audio in a buffer,
re-decode the whole buffer every ~300 ms, and show it as a partial. Text is
committed ("final") when:

  * the model's last token ended >= ENDPOINT_S before the end of the buffer
    (the speaker paused), or
  * a sentence ending in . ? ! finished >= HOLD_S before the end of the buffer
    (long continuous speech gets cut at sentence boundaries), or
  * the buffer exceeds MAX_S (forced), or the stream is flushed.

Committed audio is dropped from the buffer, so decode cost stays bounded.
All MLX calls must run on the single MLX thread (see server.py).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import mlx.core as mx
import numpy as np

SR = 16000
MODEL_ID = os.environ.get("LIVEVOICE_STT_MODEL", "mlx-community/parakeet-tdt-0.6b-v3")
ENDPOINT_S = float(os.environ.get("LIVEVOICE_ENDPOINT_S", "0.6"))
HOLD_S = 0.5
# Parakeet says "Thank you." to pure silence, so audio whose loudest 100 ms frame is
# below this RMS (about -44 dBFS) is never decoded. Raise it in a noisy room.
SILENCE_RMS = float(os.environ.get("LIVEVOICE_SILENCE_RMS", "0.006"))
MAX_S = 15.0

_model = None


def load():
    global _model
    if _model is None:
        from mlx_audio.stt.utils import load_model

        _model = load_model(MODEL_ID)
        # warm-up: the first decode compiles kernels (~1.9 s); do it before the demo
        _model.generate(mx.zeros(SR, dtype=mx.float32))
    return _model


@dataclass
class Tok:
    text: str
    start: float
    end: float


def _decode(audio: np.ndarray) -> list[list[Tok]]:
    """Return sentences as lists of tokens (times relative to audio start)."""
    res = load().generate(mx.array(audio))
    return [[Tok(t.text, t.start, t.end) for t in s.tokens] for s in res.sentences]


def _peak_rms(audio: np.ndarray, frame: int = SR // 10) -> float:
    n = len(audio) // frame
    if n == 0:
        return float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
    frames = audio[: n * frame].reshape(n, frame)
    return float(np.sqrt((frames ** 2).mean(axis=1)).max())


def _text(tokens: list[Tok]) -> str:
    return "".join(t.text for t in tokens).strip()


class StreamingTranscriber:
    def __init__(self):
        self.buf = np.zeros(0, dtype=np.float32)
        self.buf_t0 = 0.0  # absolute stream time (s) of buf[0]
        self.total = 0  # samples received
        self.last_decode_total = 0
        self.partial = ""
        self.decode_ms: list[float] = []

    def add(self, samples: np.ndarray):
        self.buf = np.concatenate([self.buf, samples.astype(np.float32)])
        self.total += len(samples)

    def due(self, every_s: float = float(os.environ.get("LIVEVOICE_DECODE_EVERY_S", "0.1"))) -> bool:
        return self.total - self.last_decode_total >= every_s * SR

    def step(self, flush: bool = False) -> dict:
        """Decode the buffer. Returns {"partial": str, "finals": [(text, abs_end_s)], "ms": float}."""
        self.last_decode_total = self.total
        dur = len(self.buf) / SR
        out = {"partial": "", "finals": [], "ms": 0.0}
        if dur < 0.3 and not flush:
            return out
        if _peak_rms(self.buf) < SILENCE_RMS:
            if dur > 1.0:
                self._cut(dur - 0.5)
            self.partial = ""
            return out
        t = time.perf_counter()
        sents = _decode(self.buf) if dur >= 0.1 else []
        out["ms"] = (time.perf_counter() - t) * 1000
        self.decode_ms.append(out["ms"])
        sents = [s for s in sents if s and _text(s)]

        if not sents:
            if dur > 4.0:  # silence / noise: keep only the last second
                self._cut(dur - 1.0)
            self.partial = ""
            return out

        last_end = sents[-1][-1].end
        n_commit = 0
        if flush or last_end <= dur - ENDPOINT_S:
            n_commit = len(sents)
        else:
            for i, s in enumerate(sents[:-1] if len(sents) > 1 else sents):
                txt = _text(s)
                if txt[-1:] in ".?!" and s[-1].end <= dur - HOLD_S:
                    n_commit = i + 1
            if n_commit == 0 and dur > MAX_S:
                n_commit = max(1, len(sents) - 1)

        if n_commit:
            committed = sents[:n_commit]
            text = " ".join(_text(s) for s in committed)
            end_rel = committed[-1][-1].end
            out["finals"].append((text, self.buf_t0 + end_rel))
            if n_commit < len(sents):
                cut = max(end_rel, sents[n_commit][0].start - 0.1)
            else:
                cut = min(dur, end_rel + 0.2)
            self._cut(cut)
            sents = sents[n_commit:]

        self.partial = " ".join(_text(s) for s in sents)
        out["partial"] = self.partial
        return out

    def _cut(self, seconds: float):
        n = int(max(0.0, seconds) * SR)
        self.buf = self.buf[n:]
        self.buf_t0 += n / SR
