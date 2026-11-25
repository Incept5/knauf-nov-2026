"""A fake model server for testing the cluster (chat-completions, Bearer key) and astra (Responses API, api-key header) code
paths without keys or network. Canned answers; the FIRST 'extract' reply per API is deliberately broken to exercise the retry.
    python3 mock_server.py            listens on http://localhost:8799/cluster/v1 and /astra/v1
    python3 test_mock.py              starts it itself and runs all three tasks on both paths"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANSWERS = {
    "summarise": {"bullets": ["a", "b", "c"], "risk": "medium", "risk_reason": "mock"},
    "extract": {"date": "2026-10-14", "site": "mock", "material": "mock", "quantity": 46, "unit": "boards", "problem": "mock", "who_must_act": []},
    "check": {"order_id": "A-1003", "product_matches": True, "ordered_qty": 50, "delivered_qty": 46, "short_qty": 4, "damaged_qty": 3,
              "consistent": False, "issues": ["short", "damaged"], "next_action": "mock"},
}
seen, requests = set(), []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        api = "astra" if self.path.startswith("/astra") else "cluster"
        requests.append({"api": api, "path": self.path, "headers": dict(self.headers), "body": body})
        ok_auth = self.headers.get("api-key") == "test-astra" if api == "astra" else self.headers.get("Authorization") == "Bearer test-cluster"
        if not ok_auth:
            return self.reply(401, {"error": "bad key"})
        messages = body["input"] if api == "astra" else body["messages"]
        first = messages[1]["content"]
        task = "summarise" if first.startswith("Summarise") else "extract" if first.startswith("Extract") else "check"
        text = json.dumps(ANSWERS[task])
        if task == "extract" and api not in seen:
            seen.add(api); text = "Sure! Here is the data: {date: 14 October}"
        if api == "astra" and self.path.endswith("/responses"):
            return self.reply(200, {"status": "completed", "output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": text}]}]})
        if api == "cluster" and self.path.endswith("/chat/completions"):
            return self.reply(200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]})
        self.reply(404, {"error": "no such path"})

    def reply(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8799), H).serve_forever()
