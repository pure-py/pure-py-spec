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

    def test_recorded_verification_preserves_generation_fingerprints(self):
        for path in (e.ROOT / "livecodebench").glob("*.json"):
            data = json.loads(path.read_text())
            if "verification" not in data:
                continue
            generation = [[task_id, condition, task[condition]["code"], task[condition].get("generation")]
                          for task_id, task in data["tasks"].items() for condition in e.CONDITIONS]
            fingerprint = e.sha(json.dumps(generation, sort_keys=True, ensure_ascii=False).encode())
            self.assertEqual(fingerprint, data["verification"]["generation_sha256"])
            for metric in ("checker", "official_tests"):
                evaluated = 0
                for task in data["tasks"].values():
                    for condition in e.CONDITIONS:
                        solution = task[condition]
                        if solution["code"]:
                            self.assertIsInstance(solution[metric]["passed"], bool)
                            evaluated += 1
                        else:
                            self.assertIsNone(solution[metric]["passed"])
                count = "checker_evaluated" if metric == "checker" else "tests_evaluated"
                self.assertEqual(evaluated, data["verification"][count])

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

    def test_prompt_requires_condition_specific_tags(self):
        for condition in e.CONDITIONS:
            prompt = e.prompt(self.task, condition)
            self.assertIn(f"<{condition}>...</{condition}>", prompt)
            self.assertIn("Do not include explanations or any text outside the tags", prompt)
            self.assertIn(self.task["signature"], prompt)

    def test_tagged_source_extraction(self):
        for condition in e.CONDITIONS:
            tagged = f"<{condition}>\n{GOOD}</{condition}>"
            cases = [(tagged, "valid", GOOD.strip()),
                     (" \n" + tagged + "\n ", "valid", GOOD.strip()),
                     ("Here is the solution:\n" + tagged + "\nExplanation.", "outside_text", GOOD.strip()),
                     (GOOD, "missing_tags", ""),
                     ("```python\n" + GOOD + "```", "missing_tags", ""),
                     (f"<{condition}>" + GOOD, "invalid_tags", ""),
                     (tagged + tagged, "invalid_tags", ""),
                     (f"<{condition}></{condition}>", "empty_code", ""),
                     (f"<{condition}>```python\n{GOOD}```</{condition}>", "markdown_fence", ""),
                     (f'<{condition}>marker = "```"</{condition}>', "valid", 'marker = "```"'),
                     (f"<{condition}>not valid Python!</{condition}>", "valid", "not valid Python!")]
            other = "purepy" if condition == "python" else "python"
            cases.extend([(f"<{other}>{GOOD}</{other}>", "invalid_tags", ""),
                          (f"<{condition}>{GOOD}</{other}>", "invalid_tags", ""),
                          (f"<{condition}><{condition}>{GOOD}</{condition}></{condition}>", "invalid_tags", ""),
                          (f'<{condition} language="python">{GOOD}</{condition}>', "invalid_tags", "")])
            for raw, status, code in cases:
                with self.subTest(condition=condition, status=status, raw=raw):
                    result = e.extract_code(raw, condition)
                    self.assertEqual(result["code"], code)
                    self.assertEqual(result["output_format"]["status"], status)
                    self.assertEqual(result["output_format"]["compliant"], status == "valid")
                    self.assertEqual(result["output_format"]["version"], e.OUTPUT_FORMAT_VERSION)

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
                condition = "purepy" if purepy else "python"
                response = f"<{condition}>\n{code}</{condition}>"
                raw = json.dumps({"choices": [{"message": {"content": response}, "finish_reason": "stop"}],
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
                self.assertEqual(data["protocol"]["output_format"], e.OUTPUT_FORMAT_VERSION)
                self.assertEqual(solution["output_format"]["status"], "valid")
                self.assertEqual(solution["attempts"][0]["raw_response"], f"<purepy>\n{BAD}</purepy>")
                self.assertEqual(len(solution["attempts"]), 2)
                self.assertEqual(solution["attempts"][0]["code"], BAD.strip())
                self.assertEqual(solution["rounds_to_acceptance"], 1)
                self.assertEqual(data["summary"]["conditions"]["purepy"]["initial"]["joint_pass"], 0)
                self.assertEqual(data["summary"]["conditions"]["purepy"]["final"]["joint_pass"], 1)
                self.assertEqual(len(requests), 3)
                feedback = requests[-1]["messages"][-1]["content"]
                self.assertIn("prohibited", feedback)
                self.assertIn("<purepy>...</purepy>", feedback)
                self.assertNotIn(self.task["official"]["test"], feedback)
                self.assertNotIn("test-only-secret", path.read_text())
                for suffix in (".md", ".svg", ".pdf", ".tex"):
                    self.assertTrue(path.with_suffix(suffix).exists())
                e.figure(path, Path(folder) / "figure/generation.pdf")
                self.assertTrue((Path(folder) / "figure/generation.pdf").exists())
                report = path.with_suffix(".md").read_text()
                self.assertIn("| HumanEval/2 | python | complete |", report)
                self.assertIn("| HumanEval/2 | purepy | complete |", report)
                self.assertIn("## Output Format", report)
                self.assertEqual(data["summary"]["conditions"]["purepy"]["final"]["format_compliant"], 1)
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
                second["protocol"]["output_format"] = "different-format"
                e.save(Path(folder) / "other.json", second)
                e.compare([path, Path(folder) / "other.json"], Path(folder) / "format-separated.json")
                self.assertEqual(len(json.loads((Path(folder) / "format-separated.json").read_text())["groups"]), 2)
                second["protocol"]["output_format"] = e.OUTPUT_FORMAT_VERSION
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
        self.assertIsNone(result["checker"]["passed"])
        self.assertIsNone(result["official_tests"]["passed"])
        self.assertEqual(result["rejections"], 0)

    def test_api_error_does_not_evaluate_partial_content(self):
        args = argparse.Namespace(base_url="http://127.0.0.1:1/v1", provider="openai", model="fake",
                                  max_tokens=100, benchmark="humaneval", repair_rounds=3)
        with patch("evaluation.request", return_value={"code": BAD, "generation": {"status": "api_error"}}), patch(
                "evaluation.check") as checker, patch("evaluation.official_tests") as tests:
            result = e.attempt_solution(args, self.task, "purepy")
        checker.assert_not_called()
        tests.assert_not_called()
        self.assertEqual(result["code"], BAD)
        self.assertEqual(result["rejections"], 0)

    def test_empty_output_stays_unevaluated(self):
        self.assertIsNone(e.check("")["passed"])
        self.assertIsNone(e.official_tests("", self.task, "humaneval")["passed"])

    def test_api_errors_have_unknown_rates_and_saved_reports(self):
        (e.ROOT / "results").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="api-error-", dir=e.ROOT / "results") as folder:
            path = Path(folder) / "fake.json"
            args = argparse.Namespace(benchmark="humaneval", model="fake", provider="openai",
                base_url="http://127.0.0.1:1/v1", max_tokens=100, repair_rounds=3,
                limit=1, difficulty=None, output=path)
            with patch("evaluation.validate_backend"), patch("evaluation.request", return_value={
                    "code": "", "generation": {"status": "api_error", "http_status": 401}}):
                with self.assertRaisesRegex(RuntimeError, "infrastructure failed"):
                    e.run(args)
            data = json.loads(path.read_text())
            self.assertEqual(data["status"], "infrastructure_failed")
            for condition in e.CONDITIONS:
                stages = data["summary"]["conditions"][condition]
                self.assertEqual(stages["checker_rejections"], {})
                for stage in ("initial", "final"):
                    self.assertEqual(stages[stage]["checker_unknown"], 1)
                    self.assertEqual(stages[stage]["tests_unknown"], 1)
            for gaps in data["summary"]["rq3"].values():
                self.assertTrue(all(value is None for value in gaps.values()))
            self.assertIn("unknown percentage points", path.with_suffix(".md").read_text())
            e.compare([path], Path(folder) / "comparison.json")
            self.assertIn("unknown", (Path(folder) / "comparison.md").read_text())

    def test_pipeline_fails_when_checker_cannot_run(self):
        (e.ROOT / "results").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="failure-", dir=e.ROOT / "results") as folder:
            path = Path(folder) / "fake.json"
            args = argparse.Namespace(benchmark="humaneval", model="fake", provider="openai",
                base_url="http://127.0.0.1:1/v1", max_tokens=100, repair_rounds=0,
                limit=1, difficulty=None, output=path)
            with patch("evaluation.validate_backend"), patch("evaluation.request", return_value={
                    "code": GOOD, "raw_response": f"<purepy>{GOOD}</purepy>",
                    "generation": {"status": "complete"}}), patch(
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
        raw = f"<purepy>{BAD}</purepy>"
        with patch("evaluation.request", return_value={"code": raw, "raw_response": raw,
                   "generation": {"status": "incomplete"}}) as request, patch(
                   "evaluation.check") as checker, patch("evaluation.official_tests") as tests:
            result = e.attempt_solution(args, self.task, "purepy")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result["code"], BAD.strip())
        self.assertEqual(result["attempts"][0]["raw_response"], raw)
        checker.assert_not_called()
        tests.assert_not_called()
        self.assertEqual(result["rejections"], 0)
        self.assertIsNone(result["official_tests"]["passed"])

    def test_unextractable_format_has_unknown_verdicts_and_no_repairs(self):
        (e.ROOT / "results").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="format-", dir=e.ROOT / "results") as folder:
            path = Path(folder) / "fake.json"
            args = argparse.Namespace(benchmark="humaneval", model="fake", provider="openai",
                base_url="http://127.0.0.1:1/v1", max_tokens=100, repair_rounds=3,
                limit=1, difficulty=None, output=path)
            with patch("evaluation.validate_backend"), patch("evaluation.request", return_value={
                    "code": GOOD, "raw_response": GOOD, "generation": {"status": "complete"}}) as request, patch(
                    "evaluation.check") as checker, patch("evaluation.official_tests") as tests:
                e.run(args)
            checker.assert_not_called()
            tests.assert_not_called()
            self.assertEqual(request.call_count, 2)
            data = json.loads(path.read_text())
            self.assertEqual(data["status"], "complete")
            for condition in e.CONDITIONS:
                solution = data["tasks"]["HumanEval/2"][condition]
                self.assertEqual(solution["attempts"][0]["raw_response"], GOOD)
                self.assertEqual(solution["output_format"]["status"], "missing_tags")
                self.assertEqual(solution["rejections"], 0)
                self.assertEqual(solution["code"], "")
                for stage in ("initial", "final"):
                    summary = data["summary"]["conditions"][condition][stage]
                    self.assertEqual(summary["format_noncompliant"], 1)
                    self.assertEqual(summary["tests_unknown"], 1)
                    self.assertEqual(summary["checker_unknown"], 1)
            self.assertIn("missing_tags", path.with_suffix(".md").read_text())
            for gaps in data["summary"]["rq3"].values():
                self.assertTrue(all(value is None for value in gaps.values()))

    def test_outside_prose_does_not_become_source_or_hide_format_violation(self):
        args = argparse.Namespace(base_url="http://127.0.0.1:1/v1", provider="openai", model="fake",
                                  max_tokens=100, benchmark="humaneval", repair_rounds=0)
        for condition in e.CONDITIONS:
            raw = f"Here is the solution:\n<{condition}>{GOOD}</{condition}>\nExplanation."
            with patch("evaluation.request", return_value={"code": raw, "raw_response": raw,
                       "generation": {"status": "complete"}}):
                result = e.attempt_solution(args, self.task, condition)
            self.assertTrue(result["checker"]["passed"])
            self.assertTrue(result["official_tests"]["passed"])
            self.assertEqual(result["output_format"]["status"], "outside_text")
            self.assertFalse(result["output_format"]["compliant"])
            self.assertEqual(result["attempts"][0]["raw_response"], raw)

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
