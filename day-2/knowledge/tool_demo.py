"""Tool calling demo: the model asks, OUR code runs a small function, the result goes back, the model answers.

    python3 tool_demo.py ["your question"] [--backend cluster|astra|local]
    python3 tool_demo.py --offline-demo [--wire chat|responses]     # scripted fake model, no network, no key

Two tools, both read-only and backed by fake local data:
    get_stock(sku)                       how many boards are in the depot
    convert_currency(amount, from, to)   fixed demo exchange rates (NOT real rates)

Tool calls were checked live on local servers (Ollama, mlx_lm.server, LM Studio). The cluster and Astra have NOT been tested live:
whether the cluster model supports tool calls depends on the vLLM server configuration. Exit code 3 = no tool was called.
"""
import argparse
import json
import sys

import tools_client
from tools_client import llm   # the shared llm.py (settings, backend names)

# ---- the "database" and the two tools. Plain functions; nothing here touches the network or the file system. ----
STOCK = {
    "PB-15F-1200": {"description": "Plasterboard 15 mm type F 1200x2000", "in_stock": 320, "unit_price_eur": 14.50},
    "PB-12-1200": {"description": "Plasterboard 12.5 mm standard 1200x2000", "in_stock": 1150, "unit_price_eur": 9.20},
    "ST-75-3000": {"description": "Steel stud 75 mm, 3000 mm", "in_stock": 0, "unit_price_eur": 4.10},
}
RATES_PER_EUR = {"EUR": 1.0, "USD": 1.08, "GBP": 0.85, "CHF": 0.95}      # invented for the demo


def get_stock(sku):
    item = STOCK.get(str(sku).upper())
    if item is None:
        return {"error": f"unknown SKU {sku!r}", "known_skus": sorted(STOCK)}
    return {"sku": str(sku).upper(), **item}


def convert_currency(amount, **kw):
    # "from" is a Python keyword, so the parameter arrives in **kw under its JSON name "from"
    src, dst = str(kw.get("from", "")).upper(), str(kw.get("to", "")).upper()
    if src not in RATES_PER_EUR or dst not in RATES_PER_EUR:
        return {"error": f"supported currencies: {sorted(RATES_PER_EUR)}"}
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        return {"error": "amount must be a number"}
    return {"amount": amount, "from": src, "to": dst, "result": round(amount / RATES_PER_EUR[src] * RATES_PER_EUR[dst], 2),
            "note": "fixed demo rates"}


# The ONLY functions the model may trigger. Anything else it asks for is refused.
TOOL_FUNCTIONS = {"get_stock": get_stock, "convert_currency": convert_currency}

TOOLS = [
    {"name": "get_stock", "description": "Look up stock level and unit price (EUR) for a product SKU.",
     "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "e.g. PB-15F-1200"}},
                    "required": ["sku"]}},
    {"name": "convert_currency", "description": "Convert an amount between EUR, USD, GBP and CHF.",
     "parameters": {"type": "object",
                    "properties": {"amount": {"type": "number"}, "from": {"type": "string"}, "to": {"type": "string"}},
                    "required": ["amount", "from", "to"]}},
]

DEFAULT_QUESTION = "How many PB-15F-1200 boards are in stock, and what would 40 of them cost in US dollars?"
SYSTEM = "You are a stock assistant. Use the tools for facts and numbers; never guess stock levels or exchange rates."


def scripted_post(wire):
    """A fake model for --offline-demo. Step 1: ask get_stock. Step 2: ask convert_currency. Step 3: write the answer."""
    def post(path, body):
        if wire == "chat":
            done = [m for m in body["messages"] if m.get("role") == "tool"]
        else:
            done = [i for i in body["input"] if i.get("type") == "function_call_output"]
        if len(done) == 0:
            return _fake_call(wire, "call_1", "get_stock", {"sku": "PB-15F-1200"})
        stock = json.loads(_result(done[0]))
        if len(done) == 1:
            return _fake_call(wire, "call_2", "convert_currency",
                              {"amount": round(40 * stock["unit_price_eur"], 2), "from": "EUR", "to": "USD"})
        conv = json.loads(_result(done[1]))
        text = (f"{stock['in_stock']} boards of {stock['sku']} are in stock. 40 boards cost {conv['amount']} EUR, "
                f"which is {conv['result']} USD at the demo rate. (Scripted fake model.)")
        if wire == "chat":
            return {"choices": [{"message": {"role": "assistant", "content": text}}]}
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}
    return post


def _result(item):
    return item["content"] if "content" in item else item["output"]


def _fake_call(wire, call_id, name, args):
    if wire == "chat":
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}
    return {"output": [{"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(args)}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    ap.add_argument("--backend", choices=list(llm.BACKENDS), default=None, help="cluster, astra or local (default: LLM_BACKEND or cluster)")
    ap.add_argument("--offline-demo", action="store_true", help="scripted fake model: shows the flow with no network")
    ap.add_argument("--wire", choices=["chat", "responses"], default="chat", help="offline demo only: which format to show")
    a = ap.parse_args()

    post, backend = None, a.backend or llm.default_backend()
    question = a.question
    if a.offline_demo:
        print(f"*** OFFLINE DEMO: a scripted fake model plays the model ({a.wire} wire format). No network. ***")
        post = scripted_post(a.wire)
        backend = "cluster" if a.wire == "chat" else "astra"
        question = DEFAULT_QUESTION
    print(f"Question: {question}\n")
    try:
        answer, trace = tools_client.run_tool_loop(question, TOOLS, TOOL_FUNCTIONS, backend, SYSTEM, post=post)
    except tools_client.ToolClientError as e:
        sys.exit(f"Tool loop failed: {e}\n(The server may not support tool calling for this model: on the cluster it is a vLLM setting; "
                 "locally try Ollama. --offline-demo shows the flow without a model.)")
    print(f"\nFinal answer: {answer}\nTool calls made: {len(trace)}")
    if not trace and not a.offline_demo:
        print("\nWARNING: the model answered WITHOUT calling any tool, so the numbers above did not come from our functions "
              "and may be invented.\nThis server or model probably ignores the `tools` parameter (or the model chose not to use it). "
              "Try another model/server (see the README: local Ollama works, LM Studio and mlx_lm.server may not), or use --offline-demo.")
        return 3


if __name__ == "__main__":
    sys.exit(main())
