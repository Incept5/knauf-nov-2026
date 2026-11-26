# Presenter demos (Day 1)

Examples shown in the room. You do not need to run any of them for the exercises.

## `live-demo-stages/`: one request at a time to a working app

Six steps of the live demo. Each folder has the `prompt.txt` that was given to the coding agent and the `index.html` it
produced, starting from the previous step. Open any `index.html` in a browser. Step 5 also has the tests the model wrote
(`npm install && npm test`).

Made with opencode and Qwen3.8 Flash-Next (effort low) on 25 November 2026, one run, unedited. All delivery data is invented.
The mistakes are left in on purpose: from step 3 a "weather unavailable" banner shows even though the weather loaded, and
the step 5 tests do not notice it.

## `logit-probabilities/`: what would the model say next?

Shows the five most likely next tokens and their probabilities, and lets you pick one. Runs locally with llama.cpp:
`./run.sh` (needs a Qwen GGUF; set `GGUF_MODEL_PATH` to yours). The defaults point at Qwen3.8-27B (about 30 GB of memory),
falling back to Qwen3.5-9B. Model downloads from Hugging Face are blocked on some company networks.

## `tts/`: German text to speech

`tts_guten_tag.py` uses multilingual Chatterbox through mlx-audio, so it needs a Mac with Apple Silicon
(`pip install mlx-audio`). `guten_tag.wav` is what it produced.
