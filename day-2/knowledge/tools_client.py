"""Tiny tool-calling client, standard library only. llm.chat() has no `tools` parameter, so this talks HTTP directly.

It speaks the two wire formats used by our two backends (settings and keys come from ../common/llm.py):
  chat       POST /chat/completions   request "tools": [{"type":"function","function":{...}}]
                                      reply message has "tool_calls"; we answer with {"role":"tool","tool_call_id":...}
  responses  POST /responses          request "tools": [{"type":"function","name":...}]
                                      reply "output" has {"type":"function_call"} items; we answer with
                                      {"type":"function_call_output","call_id":...}

THE LOOP:  ask model -> if it asks for tools, WE run them -> send results back -> repeat until it answers in text.
The model never runs anything. Our code decides what is allowed (see TOOL_FUNCTIONS and security_notes.md).

STATUS: the chat format is checked live on local servers (Ollama, mlx_lm.server, LM Studio); both formats against mock servers.
Whether tool calling works on the Incept5 cluster depends on how vLLM is configured (tool parser enabled for the model);
that has NOT been tested live. Astra (/responses) is also untested live.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import llm  # noqa: E402  (llm.settings(name): base url, model, api; llm.headers(); llm.no_think())


class ToolClientError(Exception):
    pass


def to_wire_tools(tools, api):
    """Our neutral tool list [{name, description, parameters}] -> the JSON each API expects."""
    if api == "chat":
        return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                  "parameters": t["parameters"]}} for t in tools]
    return [{"type": "function", "name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in tools]


def http_post(backend, path, body):
    """POST JSON to the backend. Raises ToolClientError with a readable message (HTTP error, 404, network)."""
    b = llm.settings(backend)
    try:
        headers = llm.headers(backend, b)          # raises SystemExit if a needed key is missing
    except SystemExit as e:
        raise ToolClientError(str(e)) from e
    req = urllib.request.Request(b["base"].rstrip("/") + path, data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=llm.TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise ToolClientError(f"HTTP {e.code} from {path}: {e.read().decode(errors='replace')[:400]}") from e
    except urllib.error.URLError as e:
        raise ToolClientError(f"cannot reach {b['base']} ({e.reason}). Is the server running, and is the network or Zscaler blocking it?") from e


def run_one_tool(name, raw_args, functions):
    """Run ONE tool the model asked for. Only functions in `functions` can run. Errors go back to the model as text."""
    func = functions.get(name)
    if func is None:
        return {"error": f"unknown tool {name!r}; available: {sorted(functions)}"}
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
        return func(**args)
    except Exception as e:                         # bad JSON, wrong arguments, or the tool itself failed
        return {"error": f"{type(e).__name__}: {e}"}


def run_tool_loop(prompt, tools, functions, backend="cluster", system=None, max_steps=5, max_tokens=1000, post=None,
                  log=print):
    """Return (final_text, trace). `post(path, body)` can replace the real HTTP call (used by offline demo and tests)."""
    b = llm.settings(backend)
    post = post or (lambda path, body: http_post(backend, path, body))
    api = b["api"]
    if api == "responses":
        try:
            return _loop_responses(prompt, tools, functions, b, system, max_steps, max_tokens, post, log)
        except ToolClientError as e:
            if not str(e).startswith("HTTP 404"):
                raise
            log("  (gateway has no /responses: falling back to /chat/completions)")
    return _loop_chat(prompt, tools, functions, b, system, max_steps, max_tokens, post, log)


def _loop_chat(prompt, tools, functions, b, system, max_steps, max_tokens, post, log):
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    trace = []
    for step in range(1, max_steps + 1):
        body = {"model": b["model"], "messages": messages, "tools": to_wire_tools(tools, "chat"),
                "max_tokens": max_tokens, "temperature": 0.1, **b.get("no_think", {})}
        msg = post("/chat/completions", body)["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            return (msg.get("content") or "").strip(), trace
        messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
        for call in calls:
            name, raw = call["function"]["name"], call["function"].get("arguments", "{}")
            result = run_one_tool(name, raw, functions)
            log(f"  step {step}: model asked for {name}({raw}) -> {json.dumps(result)}")
            trace.append((name, raw, result))
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    raise ToolClientError(f"no final answer after {max_steps} steps (the model kept asking for tools)")


def _loop_responses(prompt, tools, functions, b, system, max_steps, max_tokens, post, log):
    items = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    trace = []
    for step in range(1, max_steps + 1):
        body = {"model": b["model"], "input": items, "tools": to_wire_tools(tools, "responses"),
                "max_output_tokens": max_tokens, **b.get("no_think", {})}
        data = post("/responses", body)
        calls = [i for i in data.get("output", []) if i.get("type") == "function_call"]
        if not calls:
            return llm._responses_text(data), trace
        items += data["output"]                    # the model's own output items go back in, unchanged
        for call in calls:
            name, raw = call["name"], call.get("arguments", "{}")
            result = run_one_tool(name, raw, functions)
            log(f"  step {step}: model asked for {name}({raw}) -> {json.dumps(result)}")
            trace.append((name, raw, result))
            items.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(result)})
    raise ToolClientError(f"no final answer after {max_steps} steps (the model kept asking for tools)")
