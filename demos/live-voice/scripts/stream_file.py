"""Headless test: stream a WAV to the running server in real time, exactly as the
browser does (100 ms frames of 16 kHz int16 PCM over /ws), and print every event
with its time since the stream started.

Colour latency = event time - end of the spoken colour word, where the word's
end comes from an offline Parakeet alignment of the same file.

    uv run python scripts/stream_file.py samples/demo-en.wav [--fast]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import time

import numpy as np
import websockets

SR = 16000


def load_pcm(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ar", str(SR), "-ac", "1",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2")


def colour_word_ends(path: str) -> list[tuple[str, float]]:
    """Offline alignment: (colour word, end time in s) for each colour mention."""
    import mlx.core as mx

    from livevoice import stt
    from livevoice.colours import find_colours

    pcm = load_pcm(path).astype(np.float32) / 32768.0
    res = stt.load().generate(mx.array(pcm))
    toks = [t for s in res.sentences for t in s.tokens]
    out, pos, text = [], [], ""
    for t in toks:
        text += t.text
        pos.append((len(text), t.end))
    start = 0
    for m in find_colours(text):
        idx = text.lower().find(m[0].lower(), start)
        start = idx + len(m[0])
        # end time of the token that completes this word
        out.append((m[0], next(e for n, e in pos if n >= start)))
    return out


async def run(path: str, realtime: bool, url: str, tail_s: float):
    pcm = load_pcm(path)
    pcm = np.concatenate([pcm, np.zeros(int(tail_s * SR), dtype="<i2")])  # trailing silence
    events = []
    async with websockets.connect(url, max_size=None) as ws:
        ready = json.loads(await ws.recv())
        print("ready:", ready)
        t0 = time.time()

        async def reader():
            async for raw in ws:
                ev = json.loads(raw)
                ev["_t"] = time.time() - t0
                events.append(ev)
                k = ev["type"]
                if k == "partial":
                    continue
                if k == "translation" and not ev.get("done"):
                    continue
                print(f"{ev['_t']:6.2f}s  {k:12s} " + json.dumps({a: b for a, b in ev.items() if a not in ('_t', 'type')}, ensure_ascii=False))
                if k == "flushed":
                    flushed.set()

        flushed = asyncio.Event()
        rd = asyncio.create_task(reader())
        step = SR // 10
        for i in range(0, len(pcm), step):
            await ws.send(pcm[i:i + step].tobytes())
            if realtime:
                await asyncio.sleep(max(0, t0 + (i + step) / SR - time.time()))
        await ws.send(json.dumps({"type": "flush"}))
        await asyncio.wait_for(flushed.wait(), 60)
        # wait for outstanding translations / images
        n_final = sum(e["type"] == "final" for e in events)
        deadline = time.time() + 60
        while time.time() < deadline and sum(bool(e["type"] == "translation" and e.get("done")) for e in events) < n_final and ready.get("translate"):
            await asyncio.sleep(0.1)
        rd.cancel()
    return events


def report(events, colour_ends):
    parts = [e for e in events if e["type"] == "partial"]
    finals = [e for e in events if e["type"] == "final"]
    trans = [e for e in events if e["type"] == "translation" and e.get("done")]
    cols = [e for e in events if e["type"] == "colour"]
    asr = [e["asr_ms"] for e in parts if e["asr_ms"]]
    print("\n=== latency ===")
    if asr:
        print(f"Parakeet decode per update: median {statistics.median(asr):.0f} ms, max {max(asr)} ms, n={len(asr)}")
    if finals:
        lags = [e["lag_ms"] for e in finals]
        print(f"Final sentence after speech ended: median {statistics.median(lags):.0f} ms, range {min(lags)}-{max(lags)} ms, n={len(lags)}")
    if trans:
        print(f"Translation (worker): first token median {statistics.median(e['first_ms'] for e in trans):.0f} ms, "
              f"complete median {statistics.median(e['ms'] for e in trans):.0f} ms, max {max(e['ms'] for e in trans)} ms; "
              f"final->German on screen median {statistics.median(e['e2e_ms'] for e in trans):.0f} ms, n={len(trans)}")
    print("Colours (spoken word end from offline alignment -> first matching colour event):")
    from livevoice.colours import find_colours
    used = set()
    for w, end_t in colour_ends:
        name = find_colours(w)[0][1]
        ev = next((c for c in cols if id(c) not in used and c["name"] == name and c["_t"] > end_t - 1.0), None)
        if ev:
            used.add(id(ev))
            print(f"  '{w}' ends {end_t:.2f}s -> {name} at {ev['_t']:.2f}s ({(ev['_t'] - end_t) * 1000:+.0f} ms, {ev['src']})")
        else:
            print(f"  '{w}' ends {end_t:.2f}s -> MISSED")
    wrong = [(c["word"], c["name"], round(c["_t"], 2)) for c in cols if id(c) not in used]
    if wrong:
        print("  other colour events (mis-hearings or corrections):", wrong)
    print("\n=== transcript ===")
    for f in finals:
        tr = next((t["text"] for t in trans if t["id"] == f["id"]), "")
        print(f"  {f['text']}\n    -> {tr}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--fast", action="store_true", help="send as fast as possible (no real-time pacing)")
    ap.add_argument("--url", default="ws://127.0.0.1:8790/ws")
    ap.add_argument("--tail", type=float, default=1.5, help="seconds of silence appended")
    a = ap.parse_args()
    ends = colour_word_ends(a.wav)
    events = asyncio.run(run(a.wav, not a.fast, a.url, a.tail))
    report(events, ends)


if __name__ == "__main__":
    main()
