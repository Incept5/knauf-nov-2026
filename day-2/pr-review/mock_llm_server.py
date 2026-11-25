"""A tiny fake model server for testing review.py without a network or a key.

Run it:      python3 mock_llm_server.py            (listens on http://127.0.0.1:8099)
Point at it: export LLM_CLUSTER_BASE=http://127.0.0.1:8099/v1
             export INCEPT5_API_KEY=dummy
             python3 review.py prs/03-money-rounding.diff

It answers every request with the same reply, wrapped in a markdown fence the way models often do.
This is NOT a model. It only checks that the plumbing works.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_REVIEW = {
    "summary": "Mock reply: the server returns this text for every request.",
    "risk": "low",
    "risk_reasons": ["mock server, nothing was reviewed"],
    "findings": [],
    "recommendation": "needs_human_review",
}
FENCED = "Here is my review:\n```json\n" + json.dumps(DEFAULT_REVIEW, indent=2) + "\n```\nHope that helps!"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        self.server.requests.append({"path": self.path, "body": body, "headers": {k.lower(): v for k, v in self.headers.items()}})
        if self.server.status != 200:
            self._send(self.server.status, {"error": "mock failure"})
            return
        replies = self.server.replies
        text = replies[min(len(self.server.requests) - 1, len(replies) - 1)]
        if self.path.endswith("/responses"):                     # OpenAI Responses API (astra)
            self._send(200, {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]})
        else:                                                    # chat completions (cluster)
            self._send(200, {"choices": [{"message": {"role": "assistant", "content": text}}]})

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):                                # keep test output quiet
        pass


def start_mock(replies=None, status=200, port=0):
    """Start the server in a background thread. Returns (server, base_url). Call server.shutdown() when done."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.replies = replies or [FENCED]
    server.status = status
    server.requests = []                                         # everything the server received, for assertions
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


if __name__ == "__main__":
    srv, url = start_mock(port=8099)
    print(f"Mock model server on {url}  (Ctrl+C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
