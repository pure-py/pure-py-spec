import argparse
import base64
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import pickle
import tempfile
import threading
import unittest
from unittest.mock import patch

import evaluation as e


GOOD = "def truncate_number(number: float) -> float:\n    return number % 1.0\n"
BAD = "def truncate_number(number: float) -> float:\n    for i in range(0, 1):\n        pass\n    return number % 1.0\n"


class EvaluationTests(unittest.TestCase):
    def test_evalplus_reads_verified_files_in_both_orders(self):
        from evalplus.data import humaneval, mbpp
        modules = {"humaneval-plus": humaneval, "mbpp-plus": mbpp}
        for order in (tuple(modules), tuple(reversed(modules))):
            with self.subTest(order=order), patch.dict(os.environ), \
                    patch.object(humaneval, "HUMANEVAL_OVERRIDE_PATH", None), \
                    patch.object(mbpp, "MBPP_OVERRIDE_PATH", None):
                for name in order:
                    manifest = json.loads((e.ROOT / f"benchmarks/{name}.json").read_text())
                    path = e.ROOT / ".cache/evaluation" / manifest["url"].rsplit("/", 1)[1]
                    module = modules[name]
                    with patch.object(module, "stream_jsonl", wraps=module.stream_jsonl) as read_rows, \
                            patch.object(module, "make_cache", side_effect=AssertionError("unverified EvalPlus cache fallback")):
                        rows = e.BENCHMARKS[name]().load_rows(manifest)
                    read_rows.assert_called_once_with(str(path))
                    self.assertEqual(len(rows), manifest["total_problems"])

    def test_evalplus_rejects_unverified_downloads(self):
        from evalplus.data import humaneval, mbpp
        for name, module in (("humaneval-plus", humaneval), ("mbpp-plus", mbpp)):
            manifest = json.loads((e.ROOT / f"benchmarks/{name}.json").read_text())
            with self.subTest(benchmark=name), tempfile.TemporaryDirectory() as folder, \
                    patch("evaluation_benchmarks.CACHE", Path(folder)), \
                    patch("evaluation_benchmarks.urllib.request.urlopen", return_value=io.BytesIO(b"unverified dataset")), \
                    patch.object(module, "stream_jsonl") as read_rows:
                with self.assertRaisesRegex(RuntimeError, "download checksum mismatch"):
                    e.BENCHMARKS[name]().load_rows(manifest)
                read_rows.assert_not_called()

    def test_evalplus_distinguishes_preparation_and_candidate_failures(self):
        identity = "def probe(x):\n    return x\n"
        payload = {"candidate": identity, "reference": identity, "name": "probe", "dataset": "humaneval",
                   "inputs": base64.b64encode(pickle.dumps([[1]])).decode(), "atol": 0,
                   "output_not_none": False, "test_count": 1}
        module = (e.ROOT / "evaluation_benchmarks.py").read_text()
        cases = [
            ("valid", {}, None, True, False, None),
            ("wrong", {"candidate": "def probe(x):\n    return None\n"}, None, False, False, "fail"),
            ("exception", {"candidate": "def probe(x):\n    raise RuntimeError('candidate failed')\n"},
             None, False, False, "fail"),
            ("call_timeout", {"candidate": "def probe(x):\n    while True:\n        pass\n"},
             None, False, False, "fail"),
            ("decode", {"inputs": base64.b64encode(b"not a pickle").decode()},
             None, None, True, "UnpicklingError"),
            ("import", {}, {"evaluation_benchmarks.py": module + "\nsys.modules['evalplus.eval'] = None\n"},
             None, True, "ModuleNotFoundError"),
            ("reference", {"reference": "def probe(x):\n    raise RuntimeError('reference failed')\n"},
             None, None, True, "reference failed"),
        ]
        for name in ("humaneval-plus", "mbpp-plus"):
            benchmark = e.BENCHMARKS[name]()
            for label, changes, files, passed, tooling, diagnostic in cases:
                with self.subTest(benchmark=name, case=label):
                    verdict = benchmark.sandbox({**payload, "dataset": benchmark.dataset, **changes}, 10, files)
                    self.assertIs(verdict.passed, passed)
                    self.assertIs(verdict.tooling_error, tooling)
                    if diagnostic:
                        self.assertIn(diagnostic, verdict.error)

    def test_unknown_remains_unknown(self):
        rejected = e.failure_category(BAD, "solution.py:2:4: for loop prohibited", 1)
        self.assertEqual(rejected["category"], "excluded_by_design")
        unsupported = e.failure_category(GOOD, "keyword arguments in a call other than a constructor call", 3)
        self.assertEqual(unsupported["category"], "unsupported_feature")

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

    def test_pipeline_and_repair_feedback_with_local_fake_api(self):
        requests = []
        scenario = "repair"

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(body)
                purepy = "Solve this task in PurePy" in body["messages"][0]["content"]
                condition = "purepy" if purepy else "python"
                code = GOOD
                if scenario == "repair":
                    if purepy:
                        code = BAD if len(body["messages"]) == 1 else GOOD
                    else:
                        code = GOOD.replace("number % 1.0", "0.0")
                elif scenario in ("budget", "different_rejection", "truncated", "api_error"):
                    code = BAD if purepy else GOOD
                    if scenario == "different_rejection" and purepy and len(body["messages"]) > 1:
                        code = GOOD.replace("number % 1.0", "sum(value for value in [number]) % 1.0")
                response = f"<{condition}>\n{code}</{condition}>"
                if scenario == "untagged":
                    response = code
                elif scenario == "empty":
                    response = ""
                elif scenario == "outside_text":
                    response = "Here is the solution:\n" + response + "\nExplanation."
                raw = json.dumps({"choices": [{"message": {"content": response},
                                  "finish_reason": "length" if scenario == "truncated" else "stop"}],
                                  "id": "offline-test", "model": "fake", "usage": {"completion_tokens": 10}}).encode()
                self.send_response(401 if scenario == "api_error" else 200)
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
                args = argparse.Namespace(benchmark=e.BENCHMARKS["humaneval-plus"](), model="fake", provider="openai",
                    base_url=f"http://127.0.0.1:{server.server_port}/v1", max_tokens=1024, repair_rounds=2,
                    limit=1, difficulty=None, output=None)
                for scenario in ("repair", "budget", "different_rejection", "api_error",
                                 "truncated", "untagged", "empty", "outside_text"):
                    with self.subTest(scenario=scenario), patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-secret"}):
                        requests.clear()
                        args.output = Path(folder) / (scenario + ".json")
                        if scenario == "api_error":
                            with self.assertRaisesRegex(RuntimeError, "infrastructure failed"):
                                e.run(args)
                        else:
                            e.run(args)
                        report = args.output.with_suffix(".md").read_text()
                        self.assertIn("Benchmark: HumanEval+", report)
                        self.assertIn("Problems: 1 of 164", report)
                        self.assertNotIn("test-only-secret", report)
                        for suffix in (".pdf", ".svg", ".tex"):
                            self.assertTrue(args.output.with_suffix(suffix).is_file())
                        if scenario == "repair":
                            self.assertEqual(len(requests), 3)
                            self.assertIn("| python | final | 1/1 | 0/1 | 0/1 | 0 | 0 |", report)
                            self.assertIn("| purepy | initial | 0/1 | 1/1 | 0/1 | 0 | 0 |", report)
                            self.assertIn("| purepy | final | 1/1 | 1/1 | 1/1 | 0 | 0 |", report)
                            self.assertIn("final: 1 accepted problems; PurePy passes 1/1 (100.0%), Python passes 0/1 (0.0%)", report)
                            self.assertIn("| HumanEval/2 | purepy | complete | valid | valid | False | True | True | True | 1 |", report)
                            self.assertIn('purepy: {"excluded_by_design": 1}', report)
                            self.assertIn("for loops prohibited", requests[-1]["messages"][-1]["content"])
                            self.assertIn("| purepy | 0 | excluded_by_design | loop | True |", report)
                        elif scenario in ("budget", "different_rejection"):
                            self.assertEqual(len(requests), 4)
                            self.assertIn('purepy: {"excluded_by_design": 3}', report)
                            self.assertIn("| python | final | 1/1 | 1/1 | 1/1 | 0 | 0 |", report)
                            self.assertIn("| purepy | final | 0/1 | 1/1 | 0/1 | 0 | 0 |", report)
                            clears = "False" if scenario == "budget" else "None"
                            self.assertIn(f"| purepy | 0 | excluded_by_design | loop | {clears} |", report)
                            self.assertIn("final: no accepted PurePy answers.", report)
                        else:
                            self.assertEqual(len(requests), 2)
                            counts = "1/1 | 1/1 | 1/1 | 0 | 0" if scenario == "outside_text" else "0/1 | 0/1 | 0/1 | 1 | 1"
                            for condition in e.CONDITIONS:
                                for stage in ("initial", "final"):
                                    self.assertIn(f"| {condition} | {stage} | {counts} |", report)
                                self.assertIn(f"{condition}: {{}}", report)
                            self.assertIn({"api_error": "api_error", "truncated": "incomplete",
                                           "untagged": "missing_tags", "empty": "incomplete",
                                           "outside_text": "outside_text"}[scenario], report)
                            if scenario == "outside_text":
                                for condition in e.CONDITIONS:
                                    self.assertIn(f'| {condition} | final | 0 | 1 | 0 | {{"outside_text": 1}} |', report)
                                    source = args.output.parent / "solutions" / args.output.stem / "HumanEval-2" / f"{condition}.py"
                                    self.assertEqual(source.read_text(), GOOD)
                            else:
                                self.assertIn("unknown percentage points", report)
                e.compare([Path(folder) / (name + ".json") for name in ("repair", "api_error")],
                          Path(folder) / "comparison.json")
                comparison = (Path(folder) / "comparison.md").read_text()
                self.assertIn("# RQ3 Cross-Model Comparison", comparison)
                self.assertIn("infrastructure_failed", comparison)
                self.assertIn("unknown", comparison)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

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

    def test_published_results_match_comparison(self):
        import hashlib

        source = e.ROOT / "figures/humaneval-plus.json"
        comparison = json.loads(source.read_text())
        for group in comparison["groups"].values():
            for model in group["models"]:
                with self.subTest(model=model["model"]):
                    result = e.ROOT / model["source"]
                    self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), model["source_sha256"])
                    data = e.read_result(result)
                    self.assertEqual(e.summarize(data), model["summary"])
                    self.assertEqual(sorted(data["tasks"]), group["protocol"]["task_ids"])
                    for task in data["tasks"].values():
                        for condition in e.CONDITIONS:
                            for attempt in task[condition]["attempts"]:
                                attempt.validate(finished=True)
        with tempfile.TemporaryDirectory() as folder:
            for suffix in (".pdf", ".png"):
                output = Path(folder) / ("comparison" + suffix)
                e.figure(source, output)
                self.assertGreater(output.stat().st_size, 0)

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


if __name__ == "__main__":
    unittest.main()
