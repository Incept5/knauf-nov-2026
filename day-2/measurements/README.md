# How the numbers on the Day 2 slides were produced

Presenter scripts, not exercises. The chart is read on the cluster. The KV-cache measurement is the one thing that runs
on an Apple Silicon Mac (MLX, set `MLX_MODEL`), because it measures saving and reloading that machine's own cache.

| Script | What | Needs |
|---|---|---|
| `chart_data_munich.py <image>` | a vision model reads the data out of a chart | the cluster key |
| `render_answer_munich.py answer.md out.png` | draws that answer as the panel on the slide | `pip install pillow` (macOS fonts) |
| `measure_kv_munich.py <pdf> <cache-dir>` | prefill a document once, save the KV-cache, reload it and ask | `pip install mlx-lm pymupdf` |

The Munich report PDF is the City of Munich's copyright and is not in this repository.
