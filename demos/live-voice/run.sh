#!/usr/bin/env bash
# Live voice demo: http://localhost:8790/   (Ctrl-C to stop)
#   ./run.sh            transcript + colours + German + spectrogram
#   ./run.sh --images   also draw each sentence with FLUX.2-klein-4B (~7-9 s per image)
# Everything is local: HF_HUB_OFFLINE=1 stops any model download attempt.
set -euo pipefail
cd "$(dirname "$0")"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
[[ "${1:-}" == "--images" ]] && export LIVEVOICE_IMAGES=1
lsof -ti:"${LIVEVOICE_PORT:-8790}" | xargs kill -9 2>/dev/null || true
[[ -z "${LIVEVOICE_NO_OPEN:-}" ]] && ( for i in $(seq 1 120); do
    curl -s "localhost:${LIVEVOICE_PORT:-8790}/api/status" >/dev/null 2>&1 && { open "http://localhost:${LIVEVOICE_PORT:-8790}/"; exit; }
    sleep 1; done ) &
# first run installs the packages (needs the network); after that nothing is fetched
[[ -d .venv ]] || uv sync
exec uv run --offline live-voice
