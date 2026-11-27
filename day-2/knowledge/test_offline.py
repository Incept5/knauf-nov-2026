"""Self-tests. No network and no keys: model calls go to a tiny local mock HTTP server.   python3 -m unittest test_offline -v"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import threading
import unittest
import zlib
from unittest import mock
from http.server import BaseHTTPRequestHandler, HTTPServer

import extract_json
import rag_lib
import tool_demo
import tools_client

HERE = os.path.dirname(os.path.abspath(__file__))
llm = tools_client.llm


class MockServer:
    """Answers POSTs with whatever `handler(path, body, headers)` returns: a dict (200) or an int (that HTTP status)."""

    def __init__(self, handler):
        self.requests = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((self.path, body, dict(self.headers)))
                result = handler(self.path, body, self.headers)
                if isinstance(result, int):
                    self.send_response(result); self.end_headers(); self.wfile.write(b"{}"); return
                data = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()


def chat_reply(text=None, tool_calls=None):
    return {"choices": [{"message": {"role": "assistant", "content": text, "tool_calls": tool_calls}}]}


class MockedBackends(unittest.TestCase):
    """Base class: points both backends at a mock server and sets fake keys. Restores everything afterwards."""

    def setUp(self):
        self._saved = {n: dict(b) for n, b in llm.BACKENDS.items()}
        self._env = {k: os.environ.get(k) for k in ("INCEPT5_API_KEY", "ASTRA_KEY")}
        os.environ["INCEPT5_API_KEY"], os.environ["ASTRA_KEY"] = "test-key-not-real", "test-key-not-real"
        self.server = None

    def serve(self, handler):
        self.server = MockServer(handler)
        for b in llm.BACKENDS.values():
            b["base"] = self.server.url
        return self.server

    def tearDown(self):
        if self.server:
            self.server.close()
        for n, b in self._saved.items():
            llm.BACKENDS[n].clear(); llm.BACKENDS[n].update(b)
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


# ------------------------------------------------------------------ retrieval

def fake_embed(texts, backend=None):
    """Stand-in for the embedding model: a bag of word stems, so texts sharing words get similar vectors."""
    out = []
    for t in texts:
        v = [0.0] * 256
        for w in re.findall(r"\w+", t.split("Query:")[-1].lower()):
            v[zlib.crc32(w[:5].encode()) % 256] += 1.0
        out.append(v)
    return out


class TestRetrieval(unittest.TestCase):
    CORPUS = {"a.md": "Cats sleep a lot.\n\nCats chase mice at night.", "b.md": "Dogs bark loudly.\n\nDogs love long walks.",
              "c.md": "Pallets of plasterboard must be stored flat.\n\nStack pallets at most two high."}

    def test_retrieval_ranks_by_vector_similarity(self):
        chunks = rag_lib.build_chunks(self.CORPUS, max_chars=60, overlap_chars=0)
        with mock.patch.object(rag_lib, "embed", fake_embed):
            hits = rag_lib.retrieve(chunks, "how high can I stack pallets", k=3)
        self.assertEqual(len(hits), 3)
        self.assertEqual(hits[0][1]["file"], "c.md")
        self.assertEqual(hits, sorted(hits, key=lambda h: -h[0]))

    def test_question_gets_the_instruction_prefix_and_documents_do_not(self):
        seen = []
        chunks = rag_lib.build_chunks(self.CORPUS)
        with mock.patch.object(rag_lib, "embed", lambda t, b=None: (seen.append(list(t)), fake_embed(t))[1]):
            rag_lib.retrieve(chunks, "cats?", k=1)
        self.assertFalse(any(rag_lib.QUERY_PREFIX in t for t in seen[0]))
        self.assertEqual(seen[1], [rag_lib.QUERY_PREFIX + "cats?"])

    def test_chunking_limit_overlap_and_ids(self):
        paras = [f"Paragraph number {i} with some filler words to take space." for i in range(10)]
        chunks = rag_lib.chunk_text("\n\n".join(paras), max_chars=150, overlap_chars=100)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(len(c) <= 150 for c in chunks))
        for prev, nxt in zip(chunks, chunks[1:]):                      # last paragraph of one chunk starts the next
            self.assertEqual(prev.split("\n\n")[-1], nxt.split("\n\n")[0])
        self.assertTrue(all(p in "\n\n".join(chunks) for p in paras))  # nothing lost
        ids = [c["id"] for c in rag_lib.build_chunks({"x.md": "\n\n".join(paras)}, 150, 100)]
        self.assertEqual(ids[0], "x.md#1")

    def test_long_paragraph_is_split_at_sentences(self):
        text = " ".join(f"Sentence {i} is here." for i in range(40))
        chunks = rag_lib.chunk_text(text, max_chars=100)
        self.assertTrue(all(len(c) <= 100 for c in chunks))

    def test_real_docs_and_questions_are_consistent(self):
        docs = rag_lib.read_docs(os.path.join(HERE, "docs"))
        self.assertGreaterEqual(len(docs), 6)
        for name, text in docs.items():
            self.assertTrue(300 <= len(text.split()) <= 1500, f"{name}: {len(text.split())} words")
        with open(os.path.join(HERE, "questions.json"), encoding="utf-8") as fh:
            questions = json.load(fh)
        for q in questions:
            for f in q["expected_sources"]:
                self.assertIn(f, docs)
        self.assertIn("ignore all previous instructions", docs["release_process_note.md"])

    def test_full_context_budget_guard(self):
        with self.assertRaises(SystemExit):
            rag_lib.run_full("q", {"a.md": "x" * 1000}, budget=100, answer_fn=lambda p: ("a", 0))


class TestRagWithMockModel(MockedBackends):
    def test_rag_prompt_contains_only_retrieved_chunks_and_citation_rule(self):
        def handler(path, body, headers):
            if path.endswith("/embeddings"):
                return {"data": [{"index": i, "embedding": v} for i, v in enumerate(fake_embed(body["input"]))]}
            return chat_reply("48 hours [returns.md#1]")
        server = self.serve(handler)
        chunks = rag_lib.build_chunks({"returns.md": "Damage must be reported within 48 hours.",
                                       "other.md": "Zebras live in Africa."})
        r = rag_lib.run_rag("How soon must damage be reported?", chunks, k=1)
        sent = [r for r in server.requests if r[0].endswith("/chat/completions")][0][1]["messages"]
        self.assertIn("[returns.md#1]", sent[1]["content"])
        self.assertNotIn("Zebras", sent[1]["content"])
        self.assertIn("NOT IN SOURCES", sent[0]["content"])
        self.assertEqual(rag_lib.cited_files(r["answer"], ["returns.md", "other.md"]), ["returns.md"])


# ------------------------------------------------------------------ extraction

GOOD = {"date": "2026-10-14", "site": "Neubau Schulzentrum Nord", "material": "Plasterboard", "quantity": 46,
        "problem": "3 boards water damaged", "owner": None, "risk": "medium"}


class TestValidation(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(extract_json.validate(GOOD), [])

    def test_problems_are_reported(self):
        bad = dict(GOOD, date="14 October 2026", quantity="46", risk="severe", extra=1)
        del bad["site"]
        text = " | ".join(extract_json.validate(bad))
        for needle in ("missing required key 'site'", "'date'", "'quantity' must be a number", "'risk'", "unexpected key 'extra'"):
            self.assertIn(needle, text)

    def test_null_rules_and_bool(self):
        self.assertIn("'site' must not be null", extract_json.validate(dict(GOOD, site=None)))
        self.assertEqual(extract_json.validate(dict(GOOD, quantity=None)), [])
        self.assertTrue(extract_json.validate(dict(GOOD, quantity=True)))
        self.assertTrue(extract_json.validate([1, 2]))

    def test_parse_json_strips_fences(self):
        self.assertEqual(extract_json.parse_json('Sure!\n```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(ValueError):
            extract_json.parse_json("no json here")


class TestExtractRetry(MockedBackends):
    def test_retry_feeds_error_back_and_passes(self):
        replies = iter(['{"date": "14 Oct", "site": "S"}', json.dumps(GOOD)])
        server = self.serve(lambda p, b, h: chat_reply(next(replies)))
        obj, errors, attempts, _ = extract_json.extract("DELIVERY NOTE ...", backend="cluster")
        self.assertEqual((obj, errors, attempts), (GOOD, [], 2))
        first, second = server.requests[0][1], server.requests[1][1]
        self.assertEqual(first["response_format"], {"type": "json_object"})
        self.assertIn("JSON", first["messages"][-1]["content"])
        self.assertIn("failed validation", second["messages"][-1]["content"])
        self.assertIn("missing required key", second["messages"][-1]["content"])

    def test_first_try_pass_makes_one_call(self):
        server = self.serve(lambda p, b, h: chat_reply(json.dumps(GOOD)))
        self.assertEqual(extract_json.extract("doc", "cluster")[2], 1)
        self.assertEqual(len(server.requests), 1)

    def test_fails_after_two_attempts(self):
        server = self.serve(lambda p, b, h: chat_reply("not json at all"))
        obj, errors, attempts, _ = extract_json.extract("doc", "cluster")
        self.assertIsNone(obj)
        self.assertEqual(attempts, 2)
        self.assertEqual(len(server.requests), 2)
        self.assertIn("not valid JSON", errors[0])


# ------------------------------------------------------------------ tool calling

def chat_server_logic(path, body, headers):
    if path != "/chat/completions":
        return 404
    tool_msgs = [m for m in body["messages"] if m["role"] == "tool"]
    if not tool_msgs:
        return chat_reply(None, [{"id": "c1", "type": "function",
                                  "function": {"name": "get_stock", "arguments": '{"sku": "PB-15F-1200"}'}}])
    stock = json.loads(tool_msgs[0]["content"])
    return chat_reply(f"Stock is {stock['in_stock']}.")


def responses_server_logic(path, body, headers):
    if path != "/responses":
        return 404
    outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
    if not outputs:
        return {"output": [{"type": "reasoning", "id": "r1", "summary": []},
                           {"type": "function_call", "call_id": "c1", "name": "get_stock",
                            "arguments": '{"sku": "PB-15F-1200"}'}]}
    stock = json.loads(outputs[0]["output"])
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": f"Stock is {stock['in_stock']}."}]}]}


class TestToolLoop(MockedBackends):
    def run_loop(self, backend, **kw):
        return tools_client.run_tool_loop("stock?", tool_demo.TOOLS, tool_demo.TOOL_FUNCTIONS, backend,
                                          log=lambda *a: None, **kw)

    def test_chat_completions_format(self):
        server = self.serve(chat_server_logic)
        text, trace = self.run_loop("cluster")
        self.assertEqual(text, "Stock is 320.")
        self.assertEqual([t[0] for t in trace], ["get_stock"])
        first, second = server.requests[0], server.requests[1]
        self.assertEqual(first[1]["tools"][0]["type"], "function")
        self.assertEqual(first[1]["tools"][0]["function"]["name"], "get_stock")
        self.assertEqual(first[2]["Authorization"], "Bearer test-key-not-real")
        roles = [m["role"] for m in second[1]["messages"]]
        self.assertEqual(roles, ["user", "assistant", "tool"])
        self.assertEqual(second[1]["messages"][2]["tool_call_id"], "c1")

    def test_responses_format(self):
        server = self.serve(responses_server_logic)
        text, trace = self.run_loop("astra")
        self.assertEqual(text, "Stock is 320.")
        first, second = server.requests[0], server.requests[1]
        self.assertEqual(first[1]["tools"][0]["name"], "get_stock")          # flat, not nested under "function"
        self.assertEqual(first[2]["Api-Key"], "test-key-not-real")
        types = [i.get("type", i.get("role")) for i in second[1]["input"]]
        self.assertEqual(types, ["user", "reasoning", "function_call", "function_call_output"])
        self.assertEqual(second[1]["input"][3]["call_id"], "c1")

    def test_astra_falls_back_to_chat_when_no_responses_endpoint(self):
        server = self.serve(chat_server_logic)                  # 404s on /responses
        text, _ = self.run_loop("astra")
        self.assertEqual(text, "Stock is 320.")
        self.assertEqual(server.requests[0][0], "/responses")
        self.assertEqual(server.requests[1][0], "/chat/completions")

    def test_unknown_tool_is_refused_and_reported_to_model(self):
        calls = []

        def logic(path, body, headers):
            tool_msgs = [m for m in body["messages"] if m["role"] == "tool"]
            if not tool_msgs:
                return chat_reply(None, [{"id": "c9", "type": "function", "function": {"name": "run_shell", "arguments": '{"cmd": "ls"}'}}])
            calls.append(tool_msgs[0]["content"])
            return chat_reply("I cannot do that.")
        self.serve(logic)
        text, trace = self.run_loop("cluster")
        self.assertIn("unknown tool", calls[0])
        self.assertEqual(text, "I cannot do that.")

    def test_bad_arguments_do_not_crash(self):
        self.assertIn("error", tools_client.run_one_tool("get_stock", "{not json", tool_demo.TOOL_FUNCTIONS))
        self.assertIn("error", tools_client.run_one_tool("get_stock", '{"wrong": 1}', tool_demo.TOOL_FUNCTIONS))

    def test_loop_gives_up_after_max_steps(self):
        self.serve(lambda p, b, h: chat_reply(None, [{"id": "c", "type": "function",
                                                      "function": {"name": "get_stock", "arguments": '{"sku": "X"}'}}]))
        with self.assertRaises(tools_client.ToolClientError):
            self.run_loop("cluster", max_steps=3)

    def test_missing_key_is_a_clear_error(self):
        self.serve(chat_server_logic)
        del os.environ["INCEPT5_API_KEY"]
        with self.assertRaises(tools_client.ToolClientError):
            self.run_loop("cluster")


class TestServerIgnoresTools(MockedBackends):
    def test_demo_warns_and_exits_non_zero_when_no_tool_is_called(self):
        self.serve(lambda path, body, headers: chat_reply("There are 12 boards."))     # answers directly, ignores `tools`
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["tool_demo.py", "--backend", "cluster"]), contextlib.redirect_stdout(out):
            self.assertEqual(tool_demo.main(), 3)
        self.assertIn("WITHOUT calling any tool", out.getvalue())


class TestDemoTools(unittest.TestCase):
    def test_functions(self):
        self.assertEqual(tool_demo.get_stock("pb-15f-1200")["in_stock"], 320)
        self.assertIn("error", tool_demo.get_stock("nope"))
        self.assertEqual(tool_demo.convert_currency(100, **{"from": "EUR", "to": "USD"})["result"], 108.0)
        self.assertIn("error", tool_demo.convert_currency(1, **{"from": "EUR", "to": "XXX"}))

    def test_offline_demo_scripts_run_both_wires(self):
        for wire in ("chat", "responses"):
            out = subprocess.run([sys.executable, os.path.join(HERE, "tool_demo.py"), "--offline-demo", "--wire", wire],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("320 boards", out.stdout)
            self.assertIn("626.4 USD", out.stdout)


class TestCompareOffline(unittest.TestCase):
    def test_offline_demo_runs_without_network_or_keys(self):
        env = {k: v for k, v in os.environ.items() if k not in ("INCEPT5_API_KEY", "ASTRA_KEY")}
        out = subprocess.run([sys.executable, os.path.join(HERE, "compare_retrieval.py"), "--offline-demo"],
                             capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("CANNED", out.stdout)
        self.assertIn("RAG: 8 of 8", out.stdout)
        self.assertIn("FULL: 8 of 8", out.stdout)


if __name__ == "__main__":
    unittest.main()
