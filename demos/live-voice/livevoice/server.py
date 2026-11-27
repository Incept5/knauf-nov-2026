"""Live voice demo server: http://localhost:8790/

Browser mic -> 16 kHz int16 PCM over /ws -> Parakeet (MLX, in-process, one thread)
-> partial + final transcript, colour words -> background colour,
final sentences -> translator worker process (Qwen3.5, MLX) -> German.
Optional: final sentences -> image worker process (FLUX.2-klein via mflux).
The FFT/spectrogram is drawn in the browser (Web Audio AnalyserNode).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import stt
from .colours import find_colours

HERE = Path(__file__).parent
ROOT = HERE.parent
WEB = HERE / "web"
IMG_DIR = ROOT / "generated"
PORT = int(os.environ.get("LIVEVOICE_PORT", "8790"))
TRANSLATE = os.environ.get("LIVEVOICE_NO_TRANSLATE") != "1"
IMAGES = os.environ.get("LIVEVOICE_IMAGES") == "1"
# mflux lives in the flux2-image-gen project's venv; reuse it rather than install it twice
FLUX_PY = os.environ.get("LIVEVOICE_FLUX_PYTHON",
                         str(Path.home() / "dev/flux2-image-gen/.venv/bin/python"))

mlx_exec = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")


class Worker:
    """A child process speaking JSON lines; replies are routed to per-request callbacks."""

    def __init__(self, name: str, argv: list[str]):
        self.name, self.argv = name, argv
        self.proc = None
        self.ready = asyncio.Event()
        self.info: dict = {}
        self.callbacks: dict[int, callable] = {}
        self.next_id = 0
        self.busy = False

    async def start(self):
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        self.proc = await asyncio.create_subprocess_exec(
            *self.argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            env=env, cwd=str(ROOT), limit=1 << 20)
        asyncio.create_task(self._read())

    async def _read(self):
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                print(f"[{self.name}] worker exited", flush=True)
                return
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("ready"):
                self.info = msg
                self.ready.set()
                print(f"[{self.name}] ready: {msg}", flush=True)
                continue
            if msg.get("done"):
                self.busy = False
            cb = self.callbacks.get(msg.get("id"))
            if cb:
                await cb(msg)
                if msg.get("done"):
                    self.callbacks.pop(msg["id"], None)

    def submit(self, payload: dict, cb) -> int:
        self.next_id += 1
        rid = self.next_id
        self.callbacks[rid] = cb
        self.busy = True
        self.proc.stdin.write((json.dumps({"id": rid, **payload}) + "\n").encode())
        return rid


translator: Worker | None = None
imager: Worker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global translator, imager
    loop = asyncio.get_running_loop()
    if TRANSLATE:
        translator = Worker("translate", [sys.executable, "-m", "livevoice.translator_worker"])
        await translator.start()
    if IMAGES:
        if Path(FLUX_PY).exists():
            IMG_DIR.mkdir(exist_ok=True)
            imager = Worker("image", [FLUX_PY, str(HERE / "image_worker.py"), str(IMG_DIR)])
            await imager.start()
        else:
            print(f"[image] {FLUX_PY} not found; images disabled", flush=True)
    t = time.perf_counter()
    await loop.run_in_executor(mlx_exec, stt.load)
    print(f"[stt] {stt.MODEL_ID} loaded + warmed in {time.perf_counter() - t:.1f}s", flush=True)
    for w in (translator, imager):
        if w:
            await w.ready.wait()
    print(f"\n  Live voice demo ready: http://localhost:{PORT}/\n", flush=True)
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")
IMG_DIR.mkdir(exist_ok=True)
app.mount("/generated", StaticFiles(directory=IMG_DIR), name="generated")


@app.get("/")
async def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/status")
async def status():
    return {
        "stt": stt.MODEL_ID,
        "translate": translator.info.get("model") if translator else None,
        "images": bool(imager and imager.ready.is_set()),
    }


class Session:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.tr = stt.StreamingTranscriber()
        self.loop = asyncio.get_running_loop()
        self.decoding = False
        self.arrivals: list[tuple[int, float]] = []  # (samples received, wall time)
        self.shown: list[str] = []  # colour names already shown for the uncommitted text, in order
        self.prev_partial: list[str] = []  # colour names in the previous partial
        self.sent_id = 0
        self.last_image_t = 0.0
        self.closed = False

    async def send(self, obj):
        if self.closed:
            return
        try:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))
        except Exception:
            self.closed = True

    def wall_at(self, t_audio: float) -> float:
        """Wall-clock time at which audio time t_audio reached the server."""
        target = t_audio * stt.SR
        for n, w in self.arrivals:
            if n >= target:
                return w
        return self.arrivals[-1][1] if self.arrivals else time.time()

    def add(self, pcm16: bytes):
        a = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
        self.tr.add(a)
        self.arrivals.append((self.tr.total, time.time()))
        if len(self.arrivals) > 3000:
            self.arrivals = self.arrivals[-1500:]

    async def maybe_decode(self, flush=False):
        if self.decoding or not (flush or self.tr.due()):
            return
        self.decoding = True
        try:
            res = await self.loop.run_in_executor(mlx_exec, lambda: self.tr.step(flush))
        finally:
            self.decoding = False
        now = time.time()
        for text, end_s in res["finals"]:
            self.sent_id += 1
            sid = self.sent_id
            lag = (now - self.wall_at(end_s)) * 1000
            fc = find_colours(text)
            # don't let a late correction override a newer colour already on screen
            later = any(self.shown[len(fc):])
            new = None if later else self._colour_changes(fc)
            self.shown = self.shown[len(fc):]
            self.prev_partial = self.prev_partial[len(fc):]
            await self.send({"type": "final", "id": sid, "text": text,
                             "asr_ms": round(res["ms"]), "lag_ms": round(lag), "t": round(end_s, 2)})
            if new:
                w, name, css = new
                await self.send({"type": "colour", "word": w, "name": name, "css": css, "src": "final"})
            self.translate(sid, text)
            self.image(sid, text)
        # A partial's last word is often cut mid-word ("blau" heard as "Black" for one
        # decode), so a colour from a partial must appear in two decodes in a row
        # (0.1 s apart) before it changes the screen. Finals are stable and act at once.
        cols = find_colours(res["partial"])
        prev, self.prev_partial = self.prev_partial, [c[1] for c in cols]
        new = None
        for i, c in enumerate(cols):
            if i < len(prev) and prev[i] == c[1]:  # seen in two decodes in a row
                if i >= len(self.shown):
                    self.shown += [None] * (i + 1 - len(self.shown))
                if self.shown[i] != c[1]:
                    self.shown[i] = c[1]
                    new = c
        if new:
            w, name, css = new
            await self.send({"type": "colour", "word": w, "name": name, "css": css, "src": "partial"})
        await self.send({"type": "partial", "text": res["partial"], "asr_ms": round(res["ms"]),
                         "buf_s": round(len(self.tr.buf) / stt.SR, 1)})

    def _colour_changes(self, cols):
        """The last colour mention that is new, or that a re-decode has corrected
        (a partial heard "blau" where the full word turned out to be "gelb")."""
        changed = [c for i, c in enumerate(cols) if i >= len(self.shown) or self.shown[i] != c[1]]
        return changed[-1] if changed else None

    def translate(self, sid: int, text: str):
        if not translator or not translator.ready.is_set():
            return
        t0 = time.time()

        async def cb(msg):
            if msg.get("done"):
                await self.send({"type": "translation", "id": sid, "text": msg["text"], "done": True,
                                 "target": msg.get("target"),
                                 "ms": msg["ms"], "first_ms": msg["first_ms"],
                                 "e2e_ms": round((time.time() - t0) * 1000)})
            else:
                await self.send({"type": "translation", "id": sid, "delta": msg["delta"],
                                 "target": msg.get("target")})

        translator.submit({"text": text}, cb)

    def image(self, sid: int, text: str):
        # one image at a time; skip sentences that arrive while one is rendering
        if not imager or not imager.ready.is_set() or imager.busy or len(text.split()) < 3:
            return
        t0 = time.time()

        async def cb(msg):
            if msg.get("done"):
                await self.send({"type": "image", "id": sid, "url": msg.get("url"), "prompt": text,
                                 "ms": msg.get("ms"), "e2e_ms": round((time.time() - t0) * 1000)})

        imager.submit({"text": text}, cb)
        asyncio.create_task(self.send({"type": "image_start", "id": sid, "prompt": text}))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    s = Session(ws)
    await s.send({"type": "ready", "stt": stt.MODEL_ID,
                  "translate": translator.info.get("model") if translator else None,
                  "images": bool(imager and imager.ready.is_set())})
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes"):
                s.add(msg["bytes"])
                await s.maybe_decode()
            elif msg.get("text"):
                ctl = json.loads(msg["text"])
                if ctl.get("type") == "flush":
                    while s.decoding:
                        await asyncio.sleep(0.01)
                    await s.maybe_decode(flush=True)
                    await s.send({"type": "flushed"})
                elif ctl.get("type") == "reset":
                    s.tr = stt.StreamingTranscriber()
                    s.arrivals, s.shown, s.prev_partial = [], [], []
    except WebSocketDisconnect:
        pass
    finally:
        s.closed = True


def main():
    import uvicorn

    uvicorn.run(app, host=os.environ.get("LIVEVOICE_HOST", "127.0.0.1"), port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
