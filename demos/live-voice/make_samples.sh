#!/usr/bin/env bash
# The two spoken samples the demo can play instead of the microphone (macOS only).
set -euo pipefail
cd "$(dirname "$0")" && mkdir -p samples
make() { say -v "$1" -o samples/t.aiff "$3" && ffmpeg -y -loglevel error -i samples/t.aiff -ar 16000 -ac 1 "samples/$2" && rm samples/t.aiff; }
make Daniel demo-en.wav "Good morning. Today the sky is blue. I drive a green car. Please bring me the red folder. The wall should be light pink. Thank you for listening."
make Anna demo-de.wav "Der Himmel ist dunkelblau, das Gras ist grün und das Haus ist gelb."
