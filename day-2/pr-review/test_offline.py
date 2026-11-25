"""Tests that need no network and no key.   Run:  python3 -m unittest test_offline -v

Part 1 runs the gate against the canned answers. Part 2 starts a fake model server (mock_llm_server.py)
and checks that review.py copes with fenced JSON, bad JSON, HTTP errors and big diffs.
"""
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review as rv                                       # noqa: E402
import risk_gate                                          # noqa: E402
from diffutil import split_by_file, total_changed         # noqa: E402
from mock_llm_server import start_mock                    # noqa: E402

STANDARDS = (HERE / "sample-repo" / "CODING-STANDARDS.md").read_text()
DUMMY_KEYS = {"INCEPT5_API_KEY": "dummy-test-value", "ASTRA_KEY": "dummy-test-value"}


def diff_of(name):
    return (HERE / "prs" / f"{name}.diff").read_text()


def canned(name):
    clean, _ = rv.validate_review(rv.parse_model_json((HERE / "canned" / f"{name}.json").read_text()))
    return clean


def good_review(**changes):
    review = {"summary": "s", "risk": "low", "risk_reasons": [], "findings": [], "recommendation": "approve"}
    review.update(changes)
    return json.dumps(review)


# ------------------------------------------------------------------ part 1: the gate

class GateOnCannedAnswers(unittest.TestCase):
    EXPECTED = {
        "01-typo-docs": "auto_merge_candidate",
        "02-delivery-date-feature": "auto_merge_candidate",
        "03-money-rounding": "human_review",
        "04-security-customer-search": "block",
        "05-rename-reports": "human_review",       # the model said approve; size and missing tests overrule it
        "06-refund-endpoint": "human_review",
    }

    def test_expected_decisions(self):
        for name, expected in self.EXPECTED.items():
            with self.subTest(pr=name):
                decision, _ = risk_gate.decide(canned(name), diff_of(name))
                self.assertEqual(decision, expected)

    def test_every_pr_has_a_canned_answer(self):
        self.assertEqual({p.stem for p in (HERE / "prs").glob("*.diff")}, set(self.EXPECTED))


class GateRules(unittest.TestCase):
    def test_unparsed_model_answer_never_auto_merges(self):
        decision, reasons = risk_gate.decide(None, diff_of("01-typo-docs"))
        self.assertEqual(decision, "human_review")
        self.assertTrue(any("could not be parsed" in r for r in reasons))

    def test_model_cannot_loosen_a_rule(self):
        # The model says "approve, low, nothing found" for the pricing PR. The path rule still wins.
        decision, _ = risk_gate.decide(json.loads(good_review()), diff_of("03-money-rounding"))
        self.assertEqual(decision, "human_review")

    def test_model_can_make_the_decision_stricter(self):
        review = json.loads(good_review(recommendation="needs_human_review"))
        decision, _ = risk_gate.decide(review, diff_of("01-typo-docs"))
        self.assertEqual(decision, "human_review")
        decision, _ = risk_gate.decide(json.loads(good_review(recommendation="block")), diff_of("01-typo-docs"))
        self.assertEqual(decision, "block")

    def test_secret_in_diff_blocks_even_if_model_misses_it(self):
        decision, reasons = risk_gate.decide(json.loads(good_review()), diff_of("04-security-customer-search"))
        self.assertEqual(decision, "block")
        self.assertTrue(any("secret" in r for r in reasons))
        self.assertTrue(any("SQL" in r for r in reasons))

    def test_any_security_finding_blocks(self):
        finding = {"file": "x.py", "line": 1, "severity": "low", "category": "security",
                   "explanation": "e", "suggested_fix": "f"}
        review = json.loads(good_review(findings=[finding]))
        decision, _ = risk_gate.decide(review, diff_of("01-typo-docs"))
        self.assertEqual(decision, "block")

    def test_large_diff_needs_a_human(self):
        decision, reasons = risk_gate.decide(json.loads(good_review()), diff_of("05-rename-reports"))
        self.assertEqual(decision, "human_review")
        self.assertTrue(any("changed lines" in r for r in reasons))

    def test_incomplete_chunked_review_needs_a_human(self):
        review = json.loads(good_review(incomplete=True))
        decision, _ = risk_gate.decide(review, diff_of("01-typo-docs"))
        self.assertEqual(decision, "human_review")

    def test_empty_diff_needs_a_human(self):
        decision, _ = risk_gate.decide(json.loads(good_review()), "")
        self.assertEqual(decision, "human_review")

    def test_docs_only_change_needs_no_tests(self):
        decision, reasons = risk_gate.decide(json.loads(good_review()), diff_of("01-typo-docs"))
        self.assertEqual(decision, "auto_merge_candidate", reasons)


# ------------------------------------------------------------------ reading model answers

class ParsingTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(rv.parse_model_json('{"a": 1}'), {"a": 1})

    def test_fenced_json_with_chatter(self):
        self.assertEqual(rv.parse_model_json('Sure!\n```json\n{"a": 1}\n```\nBye'), {"a": 1})

    def test_text_around_bare_json(self):
        self.assertEqual(rv.parse_model_json('Here you go: {"a": [1, 2]} done'), {"a": [1, 2]})

    def test_trailing_comma_repaired(self):
        self.assertEqual(rv.parse_model_json('{"a": [1, 2,], }'), {"a": [1, 2]})

    def test_thinking_block_removed(self):
        self.assertEqual(rv.parse_model_json('<think>{"x": 0}</think>{"a": 1}'), {"a": 1})

    def test_garbage_gives_none(self):
        self.assertIsNone(rv.parse_model_json("I could not review this, sorry."))
        self.assertIsNone(rv.parse_model_json(""))
        self.assertIsNone(rv.parse_model_json("[1, 2, 3]"))

    def test_validation_falls_back_to_the_safe_side(self):
        clean, problems = rv.validate_review({"risk": "very low", "recommendation": "Looks Fine",
                                              "findings": [{"severity": "huge", "line": "12"}, "junk"]})
        self.assertEqual(clean["risk"], "medium")
        self.assertEqual(clean["recommendation"], "needs_human_review")
        self.assertEqual(clean["findings"][0]["severity"], "medium")
        self.assertEqual(clean["findings"][0]["line"], 12)
        self.assertEqual(len(clean["findings"]), 1)
        self.assertTrue(problems)

    def test_validation_accepts_spelling_variants(self):
        clean, _ = rv.validate_review({"risk": "High", "recommendation": "Needs human review", "findings": []})
        self.assertEqual((clean["risk"], clean["recommendation"]), ("high", "needs_human_review"))

    def test_not_a_review_gives_none(self):
        self.assertIsNone(rv.validate_review({"hello": "world"})[0])


# ------------------------------------------------------------------ part 2: review.py against a fake server

class MockServerTests(unittest.TestCase):
    def setUp(self):
        self.servers = []
        env = mock.patch.dict(os.environ, DUMMY_KEYS)
        env.start()
        self.addCleanup(env.stop)

    def serve(self, replies=None, status=200, backend="cluster"):
        server, url = start_mock(replies, status)
        self.servers.append(server)
        patch = mock.patch.dict(rv.llm.BACKENDS[backend], {"base": url})
        patch.start()
        self.addCleanup(patch.stop)
        return server

    def tearDown(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()

    def test_fenced_json_reply_is_parsed(self):
        server = self.serve()                                  # the default mock reply is wrapped in a ```json fence
        result = rv.review_diff(diff_of("01-typo-docs"), STANDARDS, "cluster")
        self.assertEqual(result["review"]["recommendation"], "needs_human_review")
        self.assertEqual(result["chunks"], 1)
        self.assertEqual(len(server.requests), 1)

    def test_prompt_contains_diff_standards_description_and_json(self):
        server = self.serve()
        rv.review_diff(diff_of("03-money-rounding"), STANDARDS, "cluster", description="10% off from 100 pieces")
        body = server.requests[0]["body"]
        text = json.dumps(body)
        self.assertIn("Money is `Decimal`", text)                # standards
        self.assertIn("bulk_unit_price", text)                   # diff
        self.assertIn("10% off from 100 pieces", text)           # description
        self.assertIn("JSON", text)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(server.requests[0]["headers"]["authorization"], "Bearer dummy-test-value")

    def test_astra_responses_api(self):
        server = self.serve(backend="astra")
        result = rv.review_diff(diff_of("01-typo-docs"), STANDARDS, "astra")
        self.assertIsNotNone(result["review"])
        self.assertTrue(server.requests[0]["path"].endswith("/responses"))
        self.assertEqual(server.requests[0]["headers"]["api-key"], "dummy-test-value")

    def test_bad_reply_is_retried_once(self):
        server = self.serve(["Sorry, I cannot do that.", good_review(summary="second try")])
        result = rv.review_diff(diff_of("01-typo-docs"), STANDARDS, "cluster")
        self.assertEqual(result["review"]["summary"], "second try")
        self.assertEqual(len(server.requests), 2)

    def test_two_bad_replies_give_none_and_gate_says_human(self):
        self.serve(["no json here", "still no json"])
        result = rv.review_diff(diff_of("01-typo-docs"), STANDARDS, "cluster")
        self.assertIsNone(result["review"])
        decision, _ = risk_gate.decide(result["review"], diff_of("01-typo-docs"))
        self.assertEqual(decision, "human_review")

    def test_http_error_becomes_review_error(self):
        self.serve(status=500)
        with self.assertRaises(rv.ReviewError) as caught:
            rv.review_diff(diff_of("01-typo-docs"), STANDARDS, "cluster")
        self.assertIn("HTTP 500", str(caught.exception))

    def test_unreachable_server_becomes_review_error(self):
        server, url = start_mock()
        server.shutdown()
        server.server_close()                                  # nothing is listening on that port any more
        with mock.patch.dict(rv.llm.BACKENDS["cluster"], {"base": url}):
            with self.assertRaises(rv.ReviewError) as caught:
                rv.review_diff(diff_of("01-typo-docs"), STANDARDS, "cluster")
        self.assertIn("cannot reach", str(caught.exception))

    def test_missing_key_becomes_review_error(self):
        with mock.patch.dict(os.environ, {"INCEPT5_API_KEY": ""}):
            with self.assertRaises(rv.ReviewError) as caught:
                rv.review_diff(diff_of("01-typo-docs"), STANDARDS, "cluster")
        self.assertIn("INCEPT5_API_KEY", str(caught.exception))

    def test_big_diff_is_chunked_by_file_and_merged(self):
        big = diff_of("05-rename-reports")
        self.assertGreater(total_changed(big), rv.CHUNK_THRESHOLD_LINES)
        replies = [good_review(summary="part one", risk="low"),
                   good_review(summary="part two", risk="high", recommendation="needs_human_review",
                               findings=[{"file": "orders/export.py", "line": 5, "severity": "high",
                                          "category": "defect", "explanation": "e", "suggested_fix": "f"}])]
        server = self.serve(replies)
        result = rv.review_diff(big, STANDARDS, "cluster")
        self.assertEqual(result["chunks"], 2)
        self.assertEqual(len(server.requests), 2)
        review = result["review"]
        self.assertEqual(review["risk"], "high")                         # highest risk wins
        self.assertEqual(review["recommendation"], "needs_human_review")  # strictest recommendation wins
        self.assertEqual(len(review["findings"]), 1)
        self.assertIn("part one", review["summary"])
        for request in server.requests:                                   # each call saw only its own file
            files_in_prompt = [p for p, _ in split_by_file(request["body"]["messages"][1]["content"].split("<diff>")[1])]
            self.assertEqual(len(files_in_prompt), 1)

    def test_unreadable_chunk_marks_review_incomplete(self):
        self.serve([good_review(), "garbage", "garbage again"])
        result = rv.review_diff(diff_of("05-rename-reports"), STANDARDS, "cluster")
        self.assertTrue(result["review"]["incomplete"])
        decision, _ = risk_gate.decide(result["review"], diff_of("05-rename-reports"))
        self.assertEqual(decision, "human_review")


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args, env=None):
        full_env = {**os.environ, **(env or {})}
        return subprocess.run([sys.executable, *args], cwd=HERE, capture_output=True, text=True, env=full_env)

    def test_run_all_offline_demo(self):
        done = self.run_cli("run_all.py", "--offline-demo")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("CANNED", done.stdout)
        self.assertIn("04-security-customer-search", done.stdout)

    def test_review_cli_end_to_end_with_mock_server(self):
        server, url = start_mock()
        try:
            env = {**DUMMY_KEYS, "LLM_CLUSTER_BASE": url}
            out = HERE / "prs" / "_cli_test_review.json"
            done = self.run_cli("review.py", "prs/03-money-rounding.diff", "--save", str(out), env=env)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("AI REVIEW", done.stdout)
            gate = self.run_cli("risk_gate.py", "prs/03-money-rounding.diff", str(out))
            self.assertEqual(gate.returncode, 1)                  # human_review
            self.assertIn("human_review", gate.stdout)
        finally:
            server.shutdown()
            server.server_close()
            (HERE / "prs" / "_cli_test_review.json").unlink(missing_ok=True)

    def test_review_cli_reports_network_failure_cleanly(self):
        env = {**DUMMY_KEYS, "LLM_CLUSTER_BASE": "http://127.0.0.1:9/v1"}      # nothing listens on port 9
        done = self.run_cli("review.py", "prs/01-typo-docs.diff", env=env)
        self.assertEqual(done.returncode, 2)
        self.assertIn("Review failed", done.stderr)
        self.assertNotIn("Traceback", done.stderr)


class SamplePullRequests(unittest.TestCase):
    def test_pr_05_is_large_and_pr_01_is_small(self):
        self.assertGreaterEqual(total_changed(diff_of("05-rename-reports")), 400)
        self.assertLess(total_changed(diff_of("01-typo-docs")), 20)

    def test_every_pr_has_a_one_line_description(self):
        for diff in (HERE / "prs").glob("*.diff"):
            lines = diff.with_suffix(".md").read_text().strip().splitlines()
            self.assertEqual(len(lines), 1, diff.name)


if __name__ == "__main__":
    unittest.main()
