#!/usr/bin/env python3
"""Ask for JSON in an exact format, then check that it parses.

    export INCEPT5_API_KEY=...
    python3 formatted_response_example.py                      # runs on the cluster
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))     # llm.py: the cluster by default
sys.dont_write_bytecode = True
from llm import chat  # noqa: E402

# --backend cluster (default) | astra
BACKEND = sys.argv[sys.argv.index("--backend") + 1] if "--backend" in sys.argv else None


def generate_formatted_response(prompt):
    try:
        return chat(prompt, backend=BACKEND, max_tokens=2000, temperature=0.3, json_mode=True)
    except (Exception, SystemExit) as e:
        print("Error:", e)
        return None


def main():
    prompt = """List the numbers from 1 to 10 and their names in
    English, French, German, Dutch, Chinese, Russian, Arabic, Polish, Hungarian.
    Provide the output in this exact JSON format:
    {
      "numbers": [
        {
          "number": 7,
          "English": "seven",
          "French": "sept",
          "German": "sieben",
          "Dutch": "zeven",
          "Chinese": "七",
          "Russian": "семь",
          "Arabic": "سبعة",
          "Polish": "siedem",
          "Hungarian": "hét"
        },
        ...and so on for numbers 1-10
      ]
    }"""

    response = generate_formatted_response(prompt)

    try:
        if response:
            parsed = json.loads(response)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print("Received non-JSON response:")
        print(response)


if __name__ == "__main__":
    main()
