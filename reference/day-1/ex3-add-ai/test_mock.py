"""All three tasks through the cluster-format and astra-format code paths against mock_server.   python3 test_mock.py"""
import os, threading, unittest
from http.server import ThreadingHTTPServer
os.environ.update(INCEPT5_API_KEY="test-cluster", ASTRA_KEY="test-astra",
                  LLM_CLUSTER_BASE="http://127.0.0.1:8798/cluster/v1", LLM_ASTRA_BASE="http://127.0.0.1:8798/astra/v1")
import mock_server, ai_features as ai


class Paths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 8798), mock_server.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def test_all_tasks_both_backends(self):
        doc = (ai.DOCS / "delivery_note.txt").read_text()
        for backend in ("cluster", "astra"):
            for task in ("summarise", "extract", "check"):
                mock_server.seen.discard(backend); mock_server.requests.clear()
                data, log = ai.run(task, doc, backend)
                self.assertIsNotNone(data, (backend, task, log))
                self.assertEqual(len(log), 2 if task == "extract" else 1)           # the broken first reply is retried once
                sent = mock_server.requests[0]
                if backend == "cluster":
                    self.assertTrue(sent["path"].endswith("/chat/completions"))
                    self.assertEqual(sent["body"]["response_format"], {"type": "json_object"})
                    self.assertEqual(sent["body"]["chat_template_kwargs"], {"enable_thinking": False})
                else:
                    self.assertTrue(sent["path"].endswith("/responses"))
                    self.assertEqual(sent["body"]["text"], {"format": {"type": "json_object"}})
                    self.assertNotIn("temperature", sent["body"])

    def test_wrong_key_is_reported_not_crashed(self):
        os.environ["ASTRA_KEY"] = "wrong"
        try:
            data, log = ai.run("summarise", "x", "astra")
        finally:
            os.environ["ASTRA_KEY"] = "test-astra"
        self.assertIsNone(data); self.assertIn("HTTP 401", log[0]["problems"][0])

    def test_validator_catches_wrong_numbers(self):
        bad = dict(mock_server.ANSWERS["check"], delivered_qty=50, short_qty=0, damaged_qty=0, consistent=True, ordered_qty=46)
        order = ai.order_for("Order ref: A-1003")
        self.assertTrue(ai.validate("check", bad, order))


if __name__ == "__main__":
    unittest.main(verbosity=2)
