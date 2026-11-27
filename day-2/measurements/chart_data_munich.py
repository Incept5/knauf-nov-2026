#!/usr/bin/env python3
"""Ask Qwen3.6-35B (vision) on the cluster for a chart's underlying data, for the Day 2 chart slide.

    export INCEPT5_API_KEY=...
    python3 chart_data_munich.py <chart.png> > answer.md
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "common"))
sys.dont_write_bytecode = True
from llm import chat, image_message  # noqa: E402

q = ("Look at this chart. Can you give me the underlying data for the graph? "
     "Answer with a short intro line, then a Markdown table with columns City, Purchasing power (EUR per inhabitant) and Colour (with an approximate hex), "
     "then a line starting with Range: that names the highest and the lowest, then one or two sentences on what stands out.")
messages = image_message(q, pathlib.Path(sys.argv[1]).read_bytes())
print(chat(None, messages=messages, max_tokens=700, temperature=0.0))
