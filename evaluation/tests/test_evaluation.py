import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import tokenize
import unittest
from unittest.mock import patch

import evaluation as e
import evaluation_sandbox


GOOD = "def truncate_number(number: float) -> float:\n    return number % 1.0\n"
BAD = "def truncate_number(number: float) -> float:\n    for i in range(0, 1):\n        pass\n    return number % 1.0\n"


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.problems, cls.manifest = e.load_problems("humaneval", 1)
        cls.task = next(iter(cls.problems.values()))

    def test_benchmark_provenance(self):
        self.assertEqual(list(self.problems), ["HumanEval/2"])
        self.assertEqual(self.manifest["total_problems"], 164)
        self.assertEqual(self.manifest["evaluated_problems"], 1)
        self.assertNotIn("python", self.task)
        self.assertNotIn("purepy", self.task)

    def test_checker_and_official_tests_are_independent(self):
        self.assertTrue(e.check(GOOD)["passed"])
        self.assertFalse(e.check(BAD)["passed"])
        self.assertTrue(e.official_tests(BAD, self.task, "humaneval")["passed"])
        self.assertFalse(e.official_tests(GOOD.replace("number % 1.0", "0.0"), self.task, "humaneval")["passed"])

    def test_missing_checker_is_tool_failure(self):
        with patch("evaluation.subprocess.run", side_effect=FileNotFoundError):
            result = e.check(GOOD)
        self.assertIsNone(result["passed"])
        self.assertTrue(result["tooling_error"])

    def test_sandbox_isolation(self):
        e.validate_backend("humaneval")

    def test_linux_command_has_no_credentials_or_home_bind(self):
        with patch("evaluation_sandbox.sys.platform", "linux"), patch("evaluation_sandbox.shutil.which", return_value="/usr/bin/bwrap"):
            command = evaluation_sandbox.command("/tmp/isolated")
        self.assertIn("--unshare-all", command)
        self.assertNotIn("--share-net", command)
        self.assertNotIn("--ro-bind / /", " ".join(command))
        self.assertNotIn(str(Path.home()), command)

    def test_unknown_remains_unknown(self):
        rejected = e.failure_category(BAD, "solution.py:2:4: for loop prohibited", 1)
        self.assertEqual(rejected["category"], "excluded_by_design")
        unsupported = e.failure_category(GOOD, "keyword arguments in a call other than a constructor call", 3)
        self.assertEqual(unsupported["category"], "unsupported_feature")

    def test_native_auth_headers_and_optional_openai_key(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"content": [{"type": "text", "text": GOOD}],
                                   "stop_reason": "end_turn", "id": "fake", "model": "fake"}).encode()

        captured = []

        def receive(req, timeout):
            captured.append(req)
            return Response()

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-secret"}), patch("evaluation.urllib.request.urlopen", side_effect=receive):
            result = e.request("https://api.anthropic.com/v1", "anthropic", "fake", [], 1024)
        self.assertEqual(captured[0].get_header("X-api-key"), "test-only-secret")
        self.assertNotIn("test-only-secret", json.dumps(result))

    def test_pipeline_and_repair_feedback_with_local_fake_api(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(body)
                purepy = "Solve this task in PurePy" in body["messages"][0]["content"]
                code = GOOD if len(body["messages"]) > 1 else BAD if purepy else GOOD.replace("number % 1.0", "0.0")
                raw = json.dumps({"choices": [{"message": {"content": code}, "finish_reason": "stop"}],
                                  "id": "offline-test", "model": "fake", "usage": {"completion_tokens": 10}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        (e.ROOT / "results").mkdir(exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="unit-", dir=e.ROOT / "results") as folder:
                path = Path(folder) / "fake.json"
                args = argparse.Namespace(benchmark="humaneval", model="fake", provider="openai",
                    base_url=f"http://127.0.0.1:{server.server_port}/v1", max_tokens=1024, repair_rounds=1,
                    limit=1, difficulty=None, output=path)
                with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-secret"}):
                    e.run(args)
                data = json.loads(path.read_text())
                self.assertEqual(data["status"], "complete")
                solution = data["tasks"]["HumanEval/2"]["purepy"]
                self.assertEqual(len(solution["attempts"]), 2)
                self.assertEqual(solution["attempts"][0]["code"], BAD.strip())
                self.assertEqual(solution["rounds_to_acceptance"], 1)
                self.assertEqual(data["summary"]["conditions"]["purepy"]["initial"]["joint_pass"], 0)
                self.assertEqual(data["summary"]["conditions"]["purepy"]["final"]["joint_pass"], 1)
                self.assertEqual(len(requests), 3)
                feedback = requests[-1]["messages"][-1]["content"]
                self.assertIn("prohibited", feedback)
                self.assertNotIn(self.task["official"]["test"], feedback)
                self.assertNotIn("test-only-secret", path.read_text())
                for suffix in (".md", ".svg", ".pdf", ".tex"):
                    self.assertTrue(path.with_suffix(suffix).exists())
                e.figure(path, Path(folder) / "figure/generation.pdf")
                self.assertTrue((Path(folder) / "figure/generation.pdf").exists())
                report = path.with_suffix(".md").read_text()
                self.assertIn("| HumanEval/2 | python | complete |", report)
                self.assertIn("| HumanEval/2 | purepy | complete |", report)
                code_folder = Path(folder) / "solutions/fake/HumanEval-2"
                self.assertEqual((code_folder / "purepy.py").read_text(), GOOD)
                self.assertEqual((code_folder / "purepy.round-0.py").read_text(), BAD)
                self.assertEqual(solution["attempts"][0]["next_round_clears_reported_feature"], True)
                second = copy.deepcopy(data)
                second["model"] = "other-model"
                e.save(Path(folder) / "other.json", second)
                e.compare([path, Path(folder) / "other.json"], Path(folder) / "compare.json")
                comparison = json.loads((Path(folder) / "compare.json").read_text())
                self.assertEqual(len(comparison["groups"]), 1)
                second["protocol"]["checker_version"] = "different-version"
                e.save(Path(folder) / "other.json", second)
                e.compare([path, Path(folder) / "other.json"], Path(folder) / "separate.json")
                self.assertEqual(len(json.loads((Path(folder) / "separate.json").read_text())["groups"]), 2)
                original = path.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "already exist"):
                    e.run(args)
                self.assertEqual(path.read_bytes(), original)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_api_error_has_no_automatic_retry(self):
        args = argparse.Namespace(base_url="http://127.0.0.1:1/v1", provider="openai", model="fake",
                                  max_tokens=100, benchmark="humaneval", repair_rounds=3)
        with patch("evaluation.request", return_value={"code": "", "generation": {"status": "api_error"}}) as request:
            result = e.attempt_solution(args, self.task, "purepy")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(result["attempts"]), 1)

    def test_pipeline_fails_when_checker_cannot_run(self):
        (e.ROOT / "results").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="failure-", dir=e.ROOT / "results") as folder:
            path = Path(folder) / "fake.json"
            args = argparse.Namespace(benchmark="humaneval", model="fake", provider="openai",
                base_url="http://127.0.0.1:1/v1", max_tokens=100, repair_rounds=0,
                limit=1, difficulty=None, output=path)
            with patch("evaluation.validate_backend"), patch("evaluation.request", return_value={
                    "code": GOOD, "raw_response": GOOD, "generation": {"status": "complete"}}), patch(
                    "evaluation.check", return_value={"passed": None, "tooling_error": True, "error": "checker missing"}):
                with self.assertRaisesRegex(RuntimeError, "infrastructure failed"):
                    e.run(args)
            data = json.loads(path.read_text())
            self.assertEqual(data["status"], "infrastructure_failed")
            self.assertIsNone(data["tasks"]["HumanEval/2"]["purepy"]["checker"]["passed"])
            self.assertTrue(path.with_suffix(".md").exists())

    def test_truncated_output_is_not_automatically_repaired(self):
        args = argparse.Namespace(base_url="http://127.0.0.1:1/v1", provider="openai", model="fake",
                                  max_tokens=100, benchmark="humaneval", repair_rounds=3)
        with patch("evaluation.request", return_value={"code": BAD, "raw_response": BAD,
                   "generation": {"status": "incomplete"}}) as request:
            result = e.attempt_solution(args, self.task, "purepy")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result["code"], BAD)

    def test_bad_api_url_cannot_be_saved(self):
        with self.assertRaisesRegex(RuntimeError, "credentials"):
            e.validate_api_url("https://user:secret@example.com/v1")
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            e.validate_api_url("http://example.com/v1")

    def test_unknown_diagnostic_does_not_claim_feature_cleared(self):
        first = {"code": BAD, "checker": {"passed": False, "failure_mode": {"category": "excluded_by_design", "restriction": "loop"}},
                 "official_tests": {"passed": True}, "generation": {"status": "complete"}, "round": 0}
        following = copy.deepcopy(first)
        following["round"] = 1
        following["checker"]["failure_mode"]["restriction"] = "mutation"
        result = e.pack_solution([first, following], "prompt")
        self.assertIsNone(result["attempts"][0]["next_round_clears_reported_feature"])

    def test_generated_prompt_examples_pass_checker(self):
        text = (e.ROOT / "prompts/purepy-v0.22.3.md").read_text()
        for part in text.split("```python\n")[1:]:
            self.assertTrue(e.check(part.split("```", 1)[0])["passed"])

    def test_no_python_code_comments(self):
        for path in [*e.ROOT.glob("*.py"), *Path(__file__).parent.glob("*.py")]:
            comments = [t for t in tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
                        if t.type == tokenize.COMMENT]
            self.assertEqual(comments, [], str(path))


if __name__ == "__main__":
    unittest.main()
