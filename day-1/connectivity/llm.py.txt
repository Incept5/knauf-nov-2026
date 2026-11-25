"""One place to talk to a model, for every exercise. Standard library only (nothing to install behind Zscaler).

    from llm import chat
    print(chat("Say hello in German"))                       # default backend (see DEFAULT_BACKEND)
    print(chat("Say hello in German", backend="astra"))
    print(chat("Say hello in German", backend="local"))
Shell:  python3 llm.py "Say hello in German" --backend local     (add --compare to ask every backend that is set up)
        python3 llm.py --check                                   (shows the settings and which backends answer)

Change a setting in the CONFIG block below, or without editing the file, with an environment variable:
    LLM_BACKEND=local            LLM_LOCAL_BASE=http://localhost:1234/v1        LLM_LOCAL_MODEL=qwen3.8-27b-mlx@4bit
    LLM_CLUSTER_BASE / LLM_CLUSTER_MODEL      LLM_ASTRA_BASE / LLM_ASTRA_MODEL      LLM_TIMEOUT=300
Never paste a key into a file. Set it in your environment:  export INCEPT5_API_KEY=...   export ASTRA_KEY=...
"""
import base64, json, os, sys, time, urllib.error, urllib.request

# ============================================================================================================
# CONFIG: the only part you normally need to edit.
# ============================================================================================================
DEFAULT_BACKEND = "cluster"          # which backend chat() uses when you do not say (or set LLM_BACKEND)

BACKENDS = {
    # --- 1. Incept5 Spark cluster: OpenAI chat-completions API, Qwen3.6-35B. Free to use; key on your handout.
    "cluster": {
        "base": "https://inference.incept5.com/v1",
        "model": "qwen3.6-35b",
        "key_env": "INCEPT5_API_KEY",            # environment variable that holds the key (None = no key needed)
        "api": "chat",                           # "chat" = /chat/completions, "responses" = /responses
        "no_think": {"chat_template_kwargs": {"enable_thinking": False}},   # sent when thinking=False (the default)
    },
    # --- 2. GPT-6 Astra: OpenAI Responses API. The address is not published: set LLM_ASTRA_BASE (see your handout).
    "astra": {
        "base": "REDACTED",
        "model": "gpt-6-astra",
        "key_env": "ASTRA_KEY",
        "api": "responses",
        "auth_header": "api-key",                # the key goes in this header, not as a Bearer token
        "no_think": {},
    },
    # --- 3. A model on your own machine. Any OpenAI-compatible local server works; pick ONE base URL:
    #        Ollama        http://localhost:11434/v1   model e.g. "qwen3.5:9b"     (switches thinking off reliably)
    #        LM Studio     http://localhost:1234/v1    model e.g. "qwen3.5-4b-mlx@4bit"  (cannot switch thinking off from the API)
    #        mlx_lm.server http://localhost:8080/v1    start: python3 -m mlx_lm.server --model <path> --port 8080
    #                                                  --chat-template-args '{"enable_thinking": false}'
    "local": {
        "base": "http://localhost:11434/v1",
        "model": "qwen3.5:9b",
        "key_env": None,
        "api": "chat",
        # Local servers differ, so we send both spellings of "thinking off"; servers ignore the one they do not know.
        "no_think": {"chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none"},
    },
}
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "180"))   # seconds to wait for one reply
# ============================================================================================================


def _setting(name, key):
    """The backend setting, with an environment-variable override: LLM_<NAME>_<KEY>."""
    return os.environ.get(f"LLM_{name.upper()}_{key.upper()}") or BACKENDS[name].get(key.lower())


def settings(name):
    """The effective settings of one backend (after environment overrides)."""
    b = dict(BACKENDS[name]); b["base"] = _setting(name, "base"); b["model"] = _setting(name, "model")
    return b


def default_backend():
    return os.environ.get("LLM_BACKEND", DEFAULT_BACKEND)


def _headers(name, b):
    if b["base"] == "REDACTED":
        raise SystemExit(f"{name}: no address set. Export LLM_{name.upper()}_BASE (see your handout).")
    h = {"Content-Type": "application/json"}
    if b["key_env"]:
        key = os.environ.get(b["key_env"])
        if not key:
            raise SystemExit(f"{b['key_env']} is not set. Export it in your shell first (it is on your handout).")
        if b.get("auth_header"):
            h[b["auth_header"]] = key
        else:
            h["Authorization"] = f"Bearer {key}"
    return h


def _post(name, b, path, body):
    req = urllib.request.Request(b["base"].rstrip("/") + path, data=json.dumps(body).encode(), headers=_headers(name, b))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404 and path == "/responses":
            return None                                   # this gateway has no /responses: caller falls back to chat
        raise SystemExit(f"{name}: HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"{name}: cannot reach {b['base']} ({e.reason}). Is the server running, and is the network or Zscaler blocking it?")
    except TimeoutError:
        raise SystemExit(f"{name}: no reply within {TIMEOUT:.0f} s (raise LLM_TIMEOUT, or use a smaller model)")


# Public helpers for code that needs to make its own requests (for example tool calling):
headers = _headers          # headers(name, settings(name)) -> request headers incl. the key
post = _post                # post(name, settings(name), "/chat/completions", body) -> parsed JSON


def no_think(name):
    """The extra request fields that switch thinking off for this backend."""
    return dict(BACKENDS[name].get("no_think", {}))


def image_message(prompt, png_bytes, backend=None):
    """One user message holding text and an image, in the format the backend expects."""
    name = backend or default_backend()
    url = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
    if BACKENDS[name]["api"] == "responses":
        content = [{"type": "input_text", "text": prompt}, {"type": "input_image", "image_url": url}]
    else:
        content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]
    return [{"role": "user", "content": content}]


def chat(prompt, backend=None, system=None, json_mode=False, max_tokens=1000, temperature=0.2, messages=None, thinking=False):
    """Send one prompt (or a full messages list) and return the reply text.

    thinking=False (default) asks the model not to think out loud first. Thinking models can spend the whole token budget
    thinking and return NOTHING; this function raises a clear error if that happens instead of returning an empty string.
    """
    name = backend or default_backend()
    if name not in BACKENDS:
        raise SystemExit(f"Unknown backend {name!r}; choose one of {', '.join(BACKENDS)}")
    b = settings(name)
    if messages is None:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    extra = {} if thinking else dict(b.get("no_think", {}))

    if b["api"] == "responses":
        body = {"model": b["model"], "input": messages, "max_output_tokens": max_tokens, **extra}
        if json_mode:
            body["text"] = {"format": {"type": "json_object"}}
        data = _post(name, b, "/responses", body)
        if data is not None:
            return _responses_text(data, name, max_tokens)
    body = {"model": b["model"], "messages": messages, "max_tokens": max_tokens, "temperature": temperature, **extra}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        data = _post(name, b, "/chat/completions", body)
    except SystemExit as e:
        # Some servers (LM Studio) reject response_format=json_object with HTTP 400: try once without it.
        if not (json_mode and "HTTP 400" in str(e) and "response_format" in str(e)):
            raise
        body.pop("response_format")
        data = _post(name, b, "/chat/completions", body)
    choice = data["choices"][0]
    text = (choice["message"].get("content") or "").strip()
    if not text and choice.get("finish_reason") == "length":
        raise SystemExit(f"{name}: the model used all {max_tokens} tokens (probably thinking) and returned nothing. "
                         "Raise max_tokens, or switch thinking off for this server (see the CONFIG block in llm.py).")
    return text


def _responses_text(data, name="astra", max_tokens=0):
    """Text of an OpenAI Responses-API reply: output_text if present, else the output_text parts."""
    text = data.get("output_text") or ""
    if not text:
        parts = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") in ("output_text", "text") and c.get("text"):
                        parts.append(c["text"])
        text = "".join(parts)
    text = text.strip()
    if not text and data.get("status") == "incomplete":
        raise SystemExit(f"{name}: the reply was cut off ({(data.get('incomplete_details') or {}).get('reason', 'incomplete')}) before any text. Raise max_tokens.")
    return text


def configured_backends():
    """Backends that can be tried now: no key needed, or the key variable is set."""
    return [n for n, b in BACKENDS.items() if settings(n)["base"] != "REDACTED" and (not b["key_env"] or os.environ.get(b["key_env"]))]


def compare(prompt, **kw):
    """Ask every configured backend; return {backend: (seconds, reply)}."""
    out = {}
    for name in configured_backends():
        t = time.time()
        try:
            out[name] = (round(time.time() - t, 2), None)
            reply = chat(prompt, backend=name, **kw)
            out[name] = (round(time.time() - t, 2), reply)
        except SystemExit as e:
            out[name] = (round(time.time() - t, 2), f"ERROR: {e}")
    return out


def check():
    """Print each backend's settings and whether it answers a tiny question (used by connectivity/test_connection.py)."""
    ok = True
    for name in BACKENDS:
        b = settings(name)
        key = "no key needed" if not b["key_env"] else (f"{b['key_env']} set" if os.environ.get(b["key_env"]) else f"{b['key_env']} NOT set")
        print(f"{name:8} {b['base']}  model={b['model']}  api={b['api']}  ({key})")
        if b["base"] == "REDACTED":
            print(f"         [skip] no address: set LLM_{name.upper()}_BASE"); continue
        if b["key_env"] and not os.environ.get(b["key_env"]):
            print("         [skip] key not set"); continue
        t = time.time()
        try:
            reply = chat("Reply with the single word: ok", backend=name, max_tokens=300)
            print(f"         [ OK ] {reply[:40]!r} in {time.time() - t:.1f}s")
        except SystemExit as e:
            ok = False; print(f"         [FAIL] {e}")
    return ok


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    be = sys.argv[sys.argv.index("--backend") + 1] if "--backend" in sys.argv else None
    if be in args:
        args.remove(be)
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
    prompt = " ".join(args) or "Reply with the single word: ok"
    if "--compare" in sys.argv:
        for n, (secs, reply) in compare(prompt).items():
            print(f"--- {n} ({secs}s)\n{reply}\n")
    else:
        print(chat(prompt, backend=be))
