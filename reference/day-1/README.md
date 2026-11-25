# Day 1 reference implementations (answers and demo fallback)

Not part of the attendee repo. Python 3 standard library only. Built and run on 25 Nov 2026 on an M5 Max (128 GB).
Most scripts find `llm.py` and the exercise data in `../../day-1/` (relative path), so keep this folder where it is.

Facilitator model (thinking off), set once per shell:

    python3 -m mlx_lm.server --model ~/.lmstudio/models/Qwen/Qwen3.8-27B-MLX-4bit --port 8093 --chat-template-args '{"enable_thinking": false}' --max-tokens 2000
    export LLM_LOCAL_BASE=http://localhost:8093/v1 LLM_LOCAL_MODEL=~/.lmstudio/models/Qwen/Qwen3.8-27B-MLX-4bit

| What | Run (from this folder) |
|---|---|
| Ex1 dashboard | `open ex1-dashboard/index.html` (works from disk; rebuild with `python3 ex1-dashboard/build.py`) |
| Ex1 check numbers | `python3 ex1-dashboard/verify_dashboard.py` (needs Node) |
| Ex1 "ask" box | `python3 ex1-dashboard/ask_server.py --backend local`, open http://localhost:8770 |
| Ex2 tests / app | `cd ex2-existing-code/order_pricing && python3 -m unittest discover -s tests -v && python3 cli.py` |
| Ex2 changes | `ex2-existing-code/CHANGES.md`, `ex2-existing-code/order_pricing.diff` |
| Ex2 model bug hunt | `python3 ex2-existing-code/bughunt.py --label NAME` |
| Ex3 one task | `python3 ex3-add-ai/ai_features.py --task check --doc delivery_note.txt --backend local` |
| Ex3 benchmark | `cd ex3-add-ai && python3 bench.py --label NAME && python3 naive_probe.py --label NAME` (results in `runs/`) |
| Ex3 cluster/astra paths, no keys | `python3 ex3-add-ai/test_mock.py` |
| Ex4 notes / 100k test | `ex4-escalation/NOTES.md`, `python3 ex4-escalation/perf_100k.py` |
| Ex5 spec and solution | `ex5-spec/SPEC.md`, `cd ex5-spec/solution && python3 -m unittest discover -s tests` |
| Ex5 plain vs spec | `ex5-spec/COMPARISON.md`; `cd ex5-spec && python3 compare_prompts.py --label mlx-27b --rescore` |
| Live demo fallback | `python3 live-demo/app.py --seed`, open http://localhost:8780 (`--offline` without internet) |
| Live demo tests | `cd live-demo && python3 -m unittest` |

`screenshot-*.png` in `ex1-dashboard/` and `live-demo/` show the expected look.

**Not tested:** the real Incept5 cluster and Astra (mock servers only), opencode/Copilot, Knauf network and laptops, Windows, a real phone
(phone layout checked by browser emulation at 390 px).
