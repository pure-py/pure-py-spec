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
        cls.benchmark = e.HumanEval()
        cls.problems, cls.manifest = cls.benchmark.load(1)
        cls.task = next(iter(cls.problems.values()))

    def test_benchmark_provenance(self):
        self.assertEqual(list(self.problems), ["HumanEval/2"])
        self.assertEqual(self.manifest["total_problems"], 164)
        self.assertEqual(self.manifest["evaluated_problems"], 1)
        self.assertNotIn("python", self.task.to_record())
        self.assertNotIn("purepy", self.task.to_record())

    def test_evalplus_references_pass_and_wrong_answers_fail(self):
        for name in ("humaneval-plus", "mbpp-plus"):
            benchmark = e.BENCHMARKS[name]()
            problems, manifest = benchmark.load(2)
            self.assertEqual(manifest["evaluated_problems"], 2)
            for task_id, task in problems.items():
                with self.subTest(task=task_id):
                    reference = benchmark.grade(benchmark.reference(task), task)
                    self.assertTrue(reference.passed, reference.error)
                    self.assertEqual(reference.tests_passed, task.test_count)
                    wrong = benchmark.grade(f"def {task.name}(*args):\n    return None\n", task)
                    self.assertFalse(wrong.passed)
                    self.assertFalse(wrong.tooling_error)
        problems, manifest = self.benchmark.load(all_problems=True)
        self.assertEqual(len(problems), 164)
        self.assertEqual(manifest["typed_interfaces"], 29)

    def test_checker_and_official_tests_are_independent(self):
        self.assertTrue(e.check(GOOD).passed)
        self.assertFalse(e.check(BAD).passed)
        self.assertTrue(self.benchmark.grade(BAD, self.task).passed)
        self.assertFalse(self.benchmark.grade(GOOD.replace("number % 1.0", "0.0"), self.task).passed)

    def test_missing_checker_is_tool_failure(self):
        with patch("evaluation.subprocess.run", side_effect=FileNotFoundError):
            result = e.check(GOOD)
        self.assertIsNone(result.passed)
        self.assertTrue(result.tooling_error)

    def test_sandbox_isolation(self):
        e.validate_backend(self.benchmark)

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
            self.assertIn(self.task.signature, prompt)

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
        scenario = "repair"

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(body)
                if scenario == "api_error":
                    self.send_response(401)
                    self.end_headers()
                    return
                purepy = "Solve this task in PurePy" in body["messages"][0]["content"]
                code = (GOOD if scenario != "repair" or len(body["messages"]) > 1 else
                        BAD if purepy else GOOD.replace("number % 1.0", "0.0"))
                condition = "purepy" if purepy else "python"
                response = f"<{condition}>\n{code}</{condition}>"
                if scenario == "untagged":
                    response = code
                elif scenario == "outside_text":
                    response = "Here is the solution:\n" + response + "\nExplanation."
                raw = json.dumps({"choices": [{"message": {"content": response},
                                  "finish_reason": "length" if scenario == "truncated" else "stop"}],
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
                args = argparse.Namespace(benchmark=self.benchmark, model="fake", provider="openai",
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
                accepted = data["summary"]["rq3_accepted"]
                self.assertEqual(accepted["initial"]["problems"], 0)
                self.assertIsNone(accepted["initial"]["python_minus_purepy_pp"])
                self.assertEqual(accepted["final"]["problems"], 1)
                self.assertEqual(accepted["final"]["purepy_tests_pass"], 1)
                self.assertEqual(accepted["final"]["python_tests_pass"], 0)
                self.assertEqual(accepted["final"]["python_minus_purepy_pp"], -100.0)
                self.assertEqual(len(requests), 3)
                feedback = requests[-1]["messages"][-1]["content"]
                self.assertIn("prohibited", feedback)
                self.assertIn("<purepy>...</purepy>", feedback)
                self.assertNotIn(self.task.test, feedback)
                self.assertNotIn("test-only-secret", path.read_text())
                for suffix in (".md", ".svg", ".pdf", ".tex"):
                    self.assertTrue(path.with_suffix(suffix).exists())
                e.figure(path, Path(folder) / "figure/generation.pdf")
                self.assertTrue((Path(folder) / "figure/generation.pdf").exists())
                report = path.with_suffix(".md").read_text()
                self.assertIn("| HumanEval/2 | python | complete |", report)
                self.assertIn("| HumanEval/2 | purepy | complete |", report)
                self.assertIn("## Output Format", report)
                self.assertIn("final: 1 accepted problems; PurePy passes 1/1 (100.0%), Python passes 0/1 (0.0%)", report)
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
                for scenario in ("api_error", "truncated", "untagged", "outside_text"):
                    with self.subTest(scenario=scenario), patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-secret"}):
                        args.output = Path(folder) / (scenario + ".json")
                        before = len(requests)
                        if scenario == "api_error":
                            with self.assertRaisesRegex(RuntimeError, "infrastructure failed"):
                                e.run(args)
                        else:
                            e.run(args)
                        self.assertEqual(len(requests) - before, 2)
                        report = args.output.with_suffix(".md").read_text()
                        for condition in e.CONDITIONS:
                            for stage in ("initial", "final"):
                                counts = "1/1 | 1/1 | 1/1 | 0 | 0" if scenario == "outside_text" else "0/1 | 0/1 | 0/1 | 1 | 1"
                                self.assertIn(f"| {condition} | {stage} | {counts} |", report)
                        self.assertIn({"api_error": "api_error", "truncated": "incomplete",
                                       "untagged": "missing_tags", "outside_text": "outside_text"}[scenario], report)
                        if scenario != "outside_text":
                            self.assertIn("unknown percentage points", report)
                        self.assertIn("python: {}", report)
                        self.assertIn("purepy: {}", report)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_api_error_has_no_automatic_retry(self):
        args = argparse.Namespace(base_url="http://127.0.0.1:1/v1", provider="openai", model="fake",
                                  max_tokens=100, benchmark=self.benchmark, repair_rounds=3)
        with patch("evaluation.request", return_value={"code": "", "generation": {"status": "api_error"}}) as request:
            result = e.attempt_solution(args, self.task, "purepy")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(result["attempts"]), 1)
        self.assertIsNone(result["checker"].passed)
        self.assertIsNone(result["official_tests"].passed)
        self.assertEqual(result["rejections"], 0)

    def test_api_error_does_not_evaluate_partial_content(self):
        args = argparse.Namespace(base_url="http://127.0.0.1:1/v1", provider="openai", model="fake",
                                  max_tokens=100, benchmark=self.benchmark, repair_rounds=3)
        with patch("evaluation.request", return_value={"code": BAD, "generation": {"status": "api_error"}}), patch(
                "evaluation.check") as checker, patch.object(self.benchmark, "grade") as tests:
            result = e.attempt_solution(args, self.task, "purepy")
        checker.assert_not_called()
        tests.assert_not_called()
        self.assertEqual(result["code"], BAD)
        self.assertEqual(result["rejections"], 0)

    def test_empty_output_stays_unevaluated(self):
        self.assertIsNone(e.check("").passed)
        self.assertIsNone(self.benchmark.grade("", self.task).passed)

    def test_api_errors_have_unknown_rates_and_saved_reports(self):
        (e.ROOT / "results").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="api-error-", dir=e.ROOT / "results") as folder:
            path = Path(folder) / "fake.json"
            args = argparse.Namespace(benchmark=self.benchmark, model="fake", provider="openai",
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
            args = argparse.Namespace(benchmark=self.benchmark, model="fake", provider="openai",
                base_url="http://127.0.0.1:1/v1", max_tokens=100, repair_rounds=0,
                limit=1, difficulty=None, output=path)
            with patch("evaluation.validate_backend"), patch("evaluation.request", return_value={
                    "code": GOOD, "raw_response": f"<purepy>{GOOD}</purepy>",
                    "generation": {"status": "complete"}}), patch(
                    "evaluation.check", return_value=e.Verdict(None, "checker missing", True)):
                with self.assertRaisesRegex(RuntimeError, "infrastructure failed"):
                    e.run(args)
            data = json.loads(path.read_text())
            self.assertEqual(data["status"], "infrastructure_failed")
            self.assertIsNone(data["tasks"]["HumanEval/2"]["purepy"]["checker"]["passed"])
            self.assertTrue(path.with_suffix(".md").exists())

    def test_truncated_output_is_not_automatically_repaired(self):
        args = argparse.Namespace(base_url="http://127.0.0.1:1/v1", provider="openai", model="fake",
                                  max_tokens=100, benchmark=self.benchmark, repair_rounds=3)
        raw = f"<purepy>{BAD}</purepy>"
        with patch("evaluation.request", return_value={"code": raw, "raw_response": raw,
                   "generation": {"status": "incomplete"}}) as request, patch(
                   "evaluation.check") as checker, patch.object(self.benchmark, "grade") as tests:
            result = e.attempt_solution(args, self.task, "purepy")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result["code"], BAD.strip())
        self.assertEqual(result["attempts"][0].raw_response, raw)
        checker.assert_not_called()
        tests.assert_not_called()
        self.assertEqual(result["rejections"], 0)
        self.assertIsNone(result["official_tests"].passed)

    def test_unextractable_format_has_unknown_verdicts_and_no_repairs(self):
        (e.ROOT / "results").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="format-", dir=e.ROOT / "results") as folder:
            path = Path(folder) / "fake.json"
            args = argparse.Namespace(benchmark=self.benchmark, model="fake", provider="openai",
                base_url="http://127.0.0.1:1/v1", max_tokens=100, repair_rounds=3,
                limit=1, difficulty=None, output=path)
            with patch("evaluation.validate_backend"), patch("evaluation.validate_problems"), patch(
                    "evaluation.request", return_value={
                    "code": GOOD, "raw_response": GOOD, "generation": {"status": "complete"}}) as request, patch(
                    "evaluation.check") as checker, patch.object(self.benchmark, "grade") as tests:
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
                                  max_tokens=100, benchmark=self.benchmark, repair_rounds=0)
        for condition in e.CONDITIONS:
            raw = f"Here is the solution:\n<{condition}>{GOOD}</{condition}>\nExplanation."
            with patch("evaluation.request", return_value={"code": raw, "raw_response": raw,
                       "generation": {"status": "complete"}}):
                result = e.attempt_solution(args, self.task, condition)
            self.assertTrue(result["checker"].passed)
            self.assertTrue(result["official_tests"].passed)
            self.assertEqual(result["output_format"]["status"], "outside_text")
            self.assertFalse(result["output_format"]["compliant"])
            self.assertEqual(result["attempts"][0].raw_response, raw)

    def test_bad_api_url_cannot_be_saved(self):
        with self.assertRaisesRegex(RuntimeError, "credentials"):
            e.validate_api_url("https://user:secret@example.com/v1")
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            e.validate_api_url("http://example.com/v1")

    def test_unknown_diagnostic_does_not_claim_feature_cleared(self):
        first = e.Attempt(code=BAD, checker=e.Verdict(False, None, False, exit_code=1,
                 failure_mode={"category": "excluded_by_design", "restriction": "loop"}),
                 official_tests=e.Verdict(True, None, False), generation={"status": "complete"},
                 round=0, messages=[], prompt_sha256="")
        following = copy.deepcopy(first)
        following.round = 1
        following.checker.failure_mode["restriction"] = "mutation"
        result = e.pack_solution([first, following], "prompt", "purepy", 1)
        self.assertIsNone(result["attempts"][0].next_round_clears_reported_feature)

    def test_attempt_json_roundtrip_preserves_optional_fields(self):
        attempt = e.Attempt(round=0, code="", generation={"status": "api_error"},
                            messages=[], prompt_sha256="")
        original = json.loads(json.dumps(attempt, default=e.encode_result))
        self.assertNotIn("raw_response", original)
        self.assertNotIn("output_format", original)
        self.assertNotIn("next_round_clears_reported_feature", original)
        for clearance in (e.Unrecorded.VALUE, None, False, True):
            with self.subTest(clearance=clearance):
                attempt.next_round_clears_reported_feature = clearance
                encoded = json.loads(json.dumps(attempt, default=e.encode_result))
                restored = e.Attempt.from_dict(encoded)
                self.assertEqual(restored, attempt)
                self.assertIsInstance(restored.checker, e.Verdict)
                self.assertIsInstance(restored.official_tests, e.Verdict)
                self.assertEqual(json.loads(json.dumps(restored, default=e.encode_result)), encoded)
                if clearance is e.Unrecorded.VALUE:
                    self.assertNotIn("next_round_clears_reported_feature", encoded)
                else:
                    self.assertIs(encoded["next_round_clears_reported_feature"], clearance)

    def test_invalid_attempt_cannot_replace_a_result(self):
        accepted = e.check(GOOD)
        valid = e.Attempt(round=0, code=GOOD, generation={"status": "complete"}, messages=[],
                          prompt_sha256="", checker=accepted, official_tests=e.Verdict(True, None, False))
        cases = [
            {"generation": {"status": "api_error"}},
            {"generation": {"status": "incomplete"}},
            {"generation": {"status": "api_error"}, "checker": e.Verdict(None, None, False)},
            {"code": ""},
            {"checker": e.Verdict(False, "rejected", False)},
            {"checker": e.Verdict(False, "rejected", False, exit_code=0)},
            {"checker": e.Verdict(True, None, False, exit_code=1)},
            {"checker": e.Verdict(False, "failed", True, exit_code=1)},
            {"official_tests": e.Verdict(False, "failed", True)},
            {"checker": e.Verdict(0, "invalid", False, exit_code=1)},
            {"official_tests": e.Verdict(0, "invalid", False)},
            {"round": -1},
            {"round": True},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.json"
            e.save(path, {"attempt": valid})
            original = path.read_bytes()
            for changes in cases:
                with self.subTest(changes=changes):
                    attempt = copy.deepcopy(valid)
                    for name, value in changes.items():
                        setattr(attempt, name, value)
                    with self.assertRaises(RuntimeError):
                        e.save(path, {"attempt": attempt})
                    self.assertEqual(path.read_bytes(), original)
                    self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_attempt_history_enforces_stopping_and_budget(self):
        accepted, rejected = e.check(GOOD), e.check(BAD)
        first = e.Attempt(round=0, code=BAD, generation={"status": "complete"}, messages=[],
                          prompt_sha256="", checker=rejected, official_tests=e.Verdict(True, None, False))
        second = copy.deepcopy(first)
        second.round = 1
        accepted_first = copy.deepcopy(first)
        accepted_first.code, accepted_first.checker = GOOD, accepted
        interrupted = copy.deepcopy(first)
        interrupted.generation = {"status": "api_error"}
        interrupted.checker = e.Verdict(None, "generation failed", False)
        interrupted.official_tests = e.Verdict(None, "generation failed", False)
        tool_failure = copy.deepcopy(first)
        tool_failure.official_tests = e.Verdict(None, "grader missing", True)
        cases = [([], "purepy", 1), ([second], "purepy", 1),
                 ([first, second], "purepy", 0), ([first, second], "python", 3),
                 ([accepted_first, second], "purepy", 1), ([interrupted, second], "purepy", 1),
                 ([tool_failure, second], "purepy", 1),
                 ([first], "purepy", 1)]
        for attempts, condition, budget in cases:
            with self.subTest(condition=condition, budget=budget, attempts=attempts):
                with self.assertRaises(RuntimeError):
                    e.pack_solution(attempts, "prompt", condition, budget)
        pending = e.Attempt(round=1, code=GOOD, generation={"status": "complete"},
                            messages=[], prompt_sha256="")
        solution = e.pack_solution([first, pending], "prompt", "purepy", 1, pending=True)
        self.assertEqual(solution["rejections"], 1)
        self.assertIsNone(solution["rounds_to_acceptance"])
        with self.assertRaisesRegex(RuntimeError, "pending"):
            e.pack_solution([first, pending], "prompt", "purepy", 1)
        pending.checker = accepted
        e.pack_solution([first, pending], "prompt", "purepy", 1, pending=True)
        with self.assertRaisesRegex(RuntimeError, "official tests verdict is still pending"):
            e.pack_solution([first, pending], "prompt", "purepy", 1)
        pending.official_tests = e.Verdict(True, None, False)
        solution = e.pack_solution([first, pending], "prompt", "purepy", 1)
        self.assertEqual(solution["rounds_to_acceptance"], 1)
        self.assertEqual(solution["rejections"], 1)

    def test_generated_prompt_examples_pass_checker(self):
        text = (e.ROOT / "prompts/purepy-v0.22.3.md").read_text()
        for part in text.split("```python\n")[1:]:
            self.assertTrue(e.check(part.split("```", 1)[0]).passed)

    def test_no_python_code_comments(self):
        for path in [*e.ROOT.glob("*.py"), *Path(__file__).parent.glob("*.py")]:
            comments = [t for t in tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
                        if t.type == tokenize.COMMENT]
            self.assertEqual(comments, [], str(path))


if __name__ == "__main__":
    unittest.main()
