"""Image worker (optional, LIVEVOICE_IMAGES=1): JSON lines on stdin/stdout.

Runs under the flux2-image-gen project's venv (~/dev/flux2-image-gen/.venv), which
already has mflux and the FLUX.2-klein weights cached, so this demo installs nothing.
Kept as a separate process so a render never blocks the live transcript.

    argv[1] = output directory
in : {"id": 4, "text": "a red balloon over the Brandenburg Gate"}
out: {"id": 4, "done": true, "url": "/generated/img-0004.png", "ms": 2100}
"""

import json
import os
import sys
import time
from pathlib import Path

OUT = Path(sys.argv[1])
MODEL = os.environ.get("LIVEVOICE_IMAGE_MODEL", "flux2-klein-4b")
QUANT = int(os.environ.get("LIVEVOICE_IMAGE_QUANT", "8"))
SIZE = int(os.environ.get("LIVEVOICE_IMAGE_SIZE", "512"))
STEPS = int(os.environ.get("LIVEVOICE_IMAGE_STEPS", "4"))
STYLE = "vivid editorial illustration, clean composition: "


def emit(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()


def main():
    from mflux.models.common.config.model_config import ModelConfig
    from mflux.models.flux2.variants.txt2img.flux2_klein import Flux2Klein

    model = Flux2Klein(quantize=QUANT, model_config=ModelConfig.from_name(MODEL))

    def render(prompt, seed=7):
        return model.generate_image(prompt=STYLE + prompt, seed=seed, num_inference_steps=STEPS,
                                    width=SIZE, height=SIZE, guidance=1.0).image

    t = time.perf_counter()
    render("a teapot", seed=1)  # warm-up
    emit({"ready": True, "model": f"{MODEL} q{QUANT} {SIZE}px {STEPS} steps",
          "warmup_ms": round((time.perf_counter() - t) * 1000)})
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = time.perf_counter()
        try:
            img = render(req["text"])
            name = f"img-{req['id']:04d}.png"
            img.save(OUT / name)
            emit({"id": req["id"], "done": True, "url": f"/generated/{name}",
                  "ms": round((time.perf_counter() - t) * 1000)})
        except Exception as e:  # keep the demo alive
            print(f"[image] {e!r}", file=sys.stderr, flush=True)
            emit({"id": req["id"], "done": True, "url": None, "error": str(e)})


if __name__ == "__main__":
    main()
