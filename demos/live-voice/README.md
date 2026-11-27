# Live voice demo (Day 2, "Demo: speech to text, colour and translation")

Apple Silicon Macs only. This is a presenter demo, not an exercise.

Speak into the laptop and the screen shows, live and fully offline:

- **the transcript** as you talk (NVIDIA Parakeet-TDT-0.6B-v3 on MLX; English, German and 23 other European languages),
- **the background colour** changing when you say a colour, in English or German ("blue", "dunkelblau", "ein grünes Auto", "light pink"),
- **a German translation** of each finished sentence (Qwen3.5-4B on MLX, thinking off). Speak German and it translates into English instead,
- **a live spectrogram and spectrum** of the microphone (the browser's Web Audio FFT, so no AI),
- optionally, **a picture of what you said** (FLUX.2-klein-4B, 4 steps, 512 px).

## Launch

```bash
./run.sh            # opens http://localhost:8790/ once the models are loaded (~10 s)
./run.sh --images   # also draw each sentence (adds ~10 s to start-up)
```

Then click **Start mic** (or press Space) and allow the microphone.

## Requirements

- An Apple Silicon Mac with `uv`. The first `./run.sh` installs the packages with `uv sync`, so run it once while online. After that it runs offline.
- Models, download them once first (`hf download <name>`); the demo itself never downloads:
  - `mlx-community/parakeet-tdt-0.6b-v3`
  - `mlx-community/Qwen3.5-4B-MLX-4bit`
  - `--images` only: `black-forest-labs/FLUX.2-klein-4B`, needs a Python with `mflux` installed: point `LIVEVOICE_FLUX_PYTHON` at it.
- Chrome or Safari on `localhost`. The microphone works without HTTPS on localhost, but not when the page is opened from another machine's IP.

## How to present it

1. Before the slide, start `./run.sh`, press F for full screen, and say "test, blue" once so the room sees it work.
2. Talk normally, drop colour words into your sentences, then switch to German for a sentence ("Der Himmel ist dunkelblau"). The translation flips to English.
3. If the mic or the room fails, press **S** to play `samples/demo-en.wav` through the same pipeline (`?sample=demo-de.wav` plays the German one). C clears the screen, K resets the colour.

## Options (environment variables)

| Variable | Default | |
|---|---|---|
| `LIVEVOICE_PORT` | `8790` |  |
| `LIVEVOICE_TRANSLATE_MODEL` | `mlx-community/Qwen3.5-4B-MLX-4bit` | `mlx-community/Qwen3.5-2B-MLX-4bit` was about twice as fast in one contended test; quality not compared |
| `LIVEVOICE_NO_TRANSLATE` | unset | `1` turns translation off |
| `LIVEVOICE_ENDPOINT_S` | `0.6` | the pause (s) that ends a sentence |
| `LIVEVOICE_IMAGE_MODEL` / `_STEPS` / `_SIZE` | `flux2-klein-4b` / `4` / `512` | |

## How it works

```
browser mic ─ AudioContext 16 kHz ─┬─ AnalyserNode ─ spectrogram canvas
                                   └─ AudioWorklet ─ 100 ms int16 frames ─ WebSocket /ws
server (FastAPI, livevoice/server.py)
  └─ one MLX thread: Parakeet re-decodes the uncommitted audio every 0.3 s  → partial text
       a sentence is committed after a 0.6 s pause, or at . ? ! once speech moves on → final
       colour words are matched on every partial (livevoice/colours.py)   → background
  └─ translator process (livevoice/translator_worker.py, Qwen3.5-4B)       → German, streamed
  └─ image process (livevoice/image_worker.py, FLUX.2-klein-4B, optional)  → picture
```

The translator and image model run in their own processes, so a translation or a render never stops the live transcript. 

## Testing without a speaker

```bash
./run.sh &   # or: HF_HUB_OFFLINE=1 uv run --offline live-voice
uv run python scripts/stream_file.py samples/demo-en.wav   # streams in real time, like the browser
```

It prints every event with its time and reports the latencies: Parakeet decode time, sentence commit delay, translation time, and how long after each colour word the background changed. Make the two sample files (also used by the S key) with `./make_samples.sh` (macOS `say` and `ffmpeg`).

## Measured latencies

Measured 2026-11-15 on the M5 Max (128 GB), with `scripts/stream_file.py` streaming `samples/demo-en.wav` (6 sentences, 4 colour words) and `demo-de.wav` (1 sentence, 3 colour words) in real time, two runs each, with no other model running. The runs were identical to within a few ms.

| What | Measured |
|---|---|
| Parakeet decode of the live buffer (every 0.1 s) | median 27–38 ms, max 45–177 ms |
| Sentence on screen after the speaker stops | median 530 ms (it waits for a 0.5–0.6 s pause by design) |
| Translation, Qwen3.5-4B 4-bit: first token / complete | median 190–225 ms / 245–310 ms (EN→DE, short sentences); 440–500 ms for the 20-word German sentence |
| Background colour after the colour word | before the next 0.1 s decode finishes; see note |
| FLUX.2-klein-4B image, 512 px, 4 steps, 8-bit | 1.45–1.57 s per image (6 images); first start-up 8–12 s |
| Server start, models already in the OS file cache | about 4 s (8–12 s more with `--images`) |

Note on colour timing: the test compares each colour event with the word's end time from an offline Parakeet alignment of the same file. Every colour arrived 30–430 ms *before* that timestamp, so the aligner's word ends run late and the true delay can't be measured this way. The colour is shown once the word has appeared in two decodes in a row (0.1 s apart); that rule stops a half-heard word flashing the wrong colour.

**These numbers need a quiet GPU.** While another MLX job was rendering images on the same Mac (Qwen-Image, 20 steps), the same tests gave: Parakeet decode 210–280 ms, translation 0.9–2.5 s, FLUX image 6.7–9.5 s. Close other model jobs and `ollama stop` any loaded model before presenting. With `--images` on, each image render also slows the transcript and translation for its 1.5 s (translation max 0.93 s instead of 0.38 s).
