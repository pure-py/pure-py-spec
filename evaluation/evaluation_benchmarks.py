from abc import ABC, abstractmethod
import ast
import base64
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import os
from pathlib import Path
import pickle
import re
import runpy
import sys
import tempfile
import traceback
import urllib.request
import warnings


ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache/evaluation"
HARNESS_SHA = "b7cb6a8a69807bb868150a61742e25d7bb5328bbe01d514471b6ec43c9fa9ed2"
MBPP_OUTPUT_NOT_NONE_TASKS = ("check_str", "text_match_three", "text_starta_endb")
SIMPLE_TYPES = {"int", "float", "bool", "str", "object"}


@dataclass(frozen=True)
class Problem:
    task_id: str
    name: str
    question: str
    signature: str
    typed_interface: bool

    def to_record(self) -> dict[str, object]:
        return {field.name: getattr(self, field.name) for field in fields(Problem)}


@dataclass(frozen=True)
class ReferenceProblem(Problem):
    canonical_solution: str


@dataclass(frozen=True)
class EvalPlusProblem(ReferenceProblem):
    inputs: list[list[object] | tuple[object, ...]]
    atol: float
    output_not_none: bool

    @property
    def test_count(self) -> int:
        return len(self.inputs)


@dataclass(frozen=True)
class LiveCodeBenchProblem(Problem):
    parameters: list[str]
    difficulty: str
    contest_date: str
    source_title: str
    platform: str
    original_starter_code: str
    tests_sha256: str
    test_count: int

    def to_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Verdict:
    passed: bool | None
    error: str | None
    tooling_error: bool
    exit_code: int | None = None
    command: list[str] | None = None
    failure_mode: dict[str, object] | None = None
    tests_passed: int | None = None
    tests_total: int | None = None

    def to_dict(self):
        return {key: value for key, value in asdict(self).items()
                if key in ("passed", "error", "tooling_error") or value is not None}


def encode_verdict(value):
    if isinstance(value, Verdict):
        return value.to_dict()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def download(url, path, expected):
    path = Path(path)
    if path.exists() and sha(path.read_bytes()) == expected:
        return path
    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read()
    if sha(raw) != expected:
        raise RuntimeError("download checksum mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".download")
    temporary.write_bytes(raw)
    temporary.replace(path)
    return path


def expressible(node):
    if isinstance(node, ast.Name):
        return node.id in SIMPLE_TYPES
    if isinstance(node, ast.Constant):
        return node.value is None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return expressible(node.left) and expressible(node.right)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        name = node.value.id
        if name in ("List", "list", "Optional"):
            return expressible(node.slice)
        if name in ("Dict", "dict") and isinstance(node.slice, ast.Tuple) and len(node.slice.elts) == 2:
            key, value = node.slice.elts
            return isinstance(key, ast.Name) and key.id == "str" and expressible(value)
        if name in ("Tuple", "tuple") and isinstance(node.slice, ast.Tuple):
            return all(expressible(item) for item in node.slice.elts)
    return False


def function_signature(source, name):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        module = ast.parse(source)
    node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)
    annotations = [argument.annotation for argument in node.args.args] + [node.returns]
    typed = all(annotation is not None and expressible(annotation) for annotation in annotations)
    signature = ast.unparse(node).splitlines()[0]
    return re.sub(r"\b(List|Tuple|Dict)\b", lambda m: m[0].lower(), signature), typed


class Benchmark(ABC):
    worker_tooling_errors = False

    @abstractmethod
    def load(self, limit=None, difficulty=None, all_problems=False) -> tuple[dict[str, Problem], dict]:
        raise NotImplementedError

    def grade(self, code, task: Problem) -> Verdict:
        if not code.strip():
            return Verdict(None, "no generated code to test", False)
        try:
            tree = ast.parse(code)
            if not any(isinstance(n, ast.FunctionDef) and n.name == task.name for n in tree.body):
                return Verdict(False, "required top-level function is missing", False)
        except SyntaxError as error:
            return Verdict(False, str(error), False)
        return self._grade(code, task)

    @abstractmethod
    def _grade(self, code, task) -> Verdict:
        raise NotImplementedError

    @abstractmethod
    def reference(self, task) -> str | None:
        raise NotImplementedError

    def sandbox(self, payload, timeout, files=None) -> Verdict:
        import evaluation_sandbox
        return evaluation_sandbox.run({"benchmark": self.key, **payload}, timeout, files)

    def health_check(self):
        pass

    def prepare_worker(self, payload):
        return None

    @abstractmethod
    def execute(self, payload, grader) -> Verdict:
        raise NotImplementedError


class JsonlBenchmark(Benchmark):
    @abstractmethod
    def load_rows(self, manifest):
        raise NotImplementedError

    def interface_source(self, row):
        return row["prompt"]

    @abstractmethod
    def problem(self, task_id, row, signature, typed) -> ReferenceProblem:
        raise NotImplementedError

    def load(self, limit=None, difficulty=None, all_problems=False):
        manifest = json.loads((ROOT / f"benchmarks/{self.key}.json").read_text())
        rows = self.load_rows(manifest)
        if len(rows) != manifest["total_problems"]:
            raise RuntimeError(f"{manifest['benchmark']} benchmark size changed")
        task_ids = list(rows) if all_problems or not manifest.get("task_ids") else manifest["task_ids"]
        task_ids = [task_id for task_id in task_ids if task_id not in manifest.get("excluded", {})]
        problems = {}
        for task_id in task_ids:
            row = rows[task_id]
            signature, typed = function_signature(self.interface_source(row), row["entry_point"])
            problems[task_id] = self.problem(task_id, row, signature, typed)
        manifest = {**manifest, "selected_problems": len(problems),
                    "typed_interfaces": sum(p.typed_interface for p in problems.values())}
        chosen = dict(list(problems.items())[:limit])
        return chosen, {**manifest, "evaluated_problems": len(chosen),
                        "evaluated_typed_interfaces": sum(p.typed_interface for p in chosen.values())}

    def reference(self, task) -> str:
        return task.question + task.canonical_solution


class EvalPlus(JsonlBenchmark):
    def load_rows(self, manifest):
        path = download(manifest["url"], CACHE / manifest["url"].rsplit("/", 1)[1], manifest["sha256"])
        os.environ[self.override_path] = str(path)
        return self.dataset_rows()

    @abstractmethod
    def dataset_rows(self):
        raise NotImplementedError

    def problem(self, task_id, row, signature, typed) -> EvalPlusProblem:
        inputs = [list(group.values()) if isinstance(group, dict) else group
                  for group in (row["base_input"], row["plus_input"])]
        return EvalPlusProblem(task_id=task_id, name=row["entry_point"], question=row["prompt"],
                               signature=signature, typed_interface=typed,
                               canonical_solution=row["canonical_solution"], inputs=inputs[0] + inputs[1],
                               atol=row["atol"], output_not_none=row["entry_point"] in MBPP_OUTPUT_NOT_NONE_TASKS)

    def _grade(self, code, task) -> Verdict:
        return self.sandbox({"candidate": code, "name": task.name, "reference": self.reference(task),
                             "dataset": self.dataset, "atol": task.atol,
                             "inputs": base64.b64encode(pickle.dumps(task.inputs)).decode(),
                             "test_count": task.test_count, "output_not_none": task.output_not_none}, 90)

    def health_check(self):
        identity = "def probe(x):\n    return x\n"
        probe = {"reference": identity, "candidate": identity, "name": "probe",
                 "inputs": base64.b64encode(pickle.dumps([[1], [2.5], [(1, 2)]])).decode(), "atol": 0,
                 "dataset": "humaneval", "output_not_none": False}
        wrong = {**probe, "candidate": "def probe(x):\n    return None\n"}
        if (self.sandbox(probe, 10).passed is not True
                or self.sandbox(wrong, 10).passed is not False):
            raise RuntimeError("EvalPlus test runner health check failed")

    def prepare_worker(self, payload):
        tempfile.tempdir = payload["directory"]

    def execute(self, payload, grader) -> Verdict:
        import multiprocessing
        from evalplus.eval import untrusted_check
        from evalplus.gen.util import trusted_exec
        multiprocessing.set_start_method("fork", force=True)
        if sys.platform == "darwin":
            os.environ["EVALPLUS_MAX_MEMORY_BYTES"] = "-1"
        inputs = pickle.loads(base64.b64decode(payload["inputs"]))
        try:
            expected, times = trusted_exec(payload["reference"], inputs, payload["name"], record_time=True,
                                           output_not_none=payload["output_not_none"])
        except BaseException:
            return Verdict(None, "reference solution failed: " + traceback.format_exc().strip()[-500:], True)
        status, details = untrusted_check(payload["dataset"], payload["candidate"], inputs, payload["name"],
                                          expected, payload["atol"], times)
        passed = sum(bool(d) for d in details)
        failed = next((i for i, d in enumerate(details) if not d), None)
        error = None if status == "pass" else (
            f"{status}: input {failed} {inputs[failed]!r:.200}" if failed is not None else status)
        return Verdict(status == "pass", error, False, tests_passed=passed, tests_total=len(inputs))


class HumanEvalPlus(EvalPlus):
    key = "humaneval-plus"
    name = "HumanEval+"
    dataset = "humaneval"
    override_path = "HUMANEVAL_OVERRIDE_PATH"

    def dataset_rows(self):
        from evalplus.data import get_human_eval_plus
        return get_human_eval_plus()


class MBPPPlus(EvalPlus):
    key = "mbpp-plus"
    name = "MBPP+"
    dataset = "mbpp"
    override_path = "MBPP_OVERRIDE_PATH"

    def dataset_rows(self):
        from evalplus.data import get_mbpp_plus
        return get_mbpp_plus()

    def interface_source(self, row):
        return row["canonical_solution"]


class LiveCodeBench(Benchmark):
    key = "livecodebench"
    name = "LiveCodeBench"
    worker_tooling_errors = True

    def load(self, limit=None, difficulty=None, all_problems=False):
        import livecodebench as lcb
        lcb.prepare(set())
        data = json.loads(lcb.TASKS.read_text())
        download("https://raw.githubusercontent.com/LiveCodeBench/LiveCodeBench/"
                 + lcb.HARNESS_REVISION + "/lcb_runner/evaluation/testing_util.py",
                 CACHE / "lcb-grader.py", HARNESS_SHA)
        problems = {k: LiveCodeBenchProblem(task_id=k, typed_interface=True, **v) for k, v in data["tasks"].items()
                    if not difficulty or v["difficulty"] == difficulty}
        manifest = {**data["manifest"], "selection_sha256": sha(lcb.TASKS.read_bytes()),
                    "total_problems": 1055, "selected_problems": len(problems),
                    "scope": "Typed call-based subset of release_v6; 1055 release problems in total."}
        chosen = dict(list(problems.items())[:limit])
        lcb.prepare(set(chosen))
        for task_id, task in chosen.items():
            if sha(lcb.case_path(task_id).read_bytes()) != task.tests_sha256:
                raise RuntimeError("LiveCodeBench test fixture checksum mismatch")
        return chosen, {**manifest, "evaluated_problems": len(chosen),
                        "evaluated_typed_interfaces": sum(p.typed_interface for p in chosen.values())}

    def _grade(self, code, task) -> Verdict:
        import livecodebench as lcb
        fixture = json.loads(lcb.case_path(task.task_id).read_text())
        alias = "_lcb_core_" + sha(task.task_id.encode())[:12]
        parameters = ", ".join(task.parameters)
        signature = "self" + (", " + parameters if parameters else "")
        adapted = code + f"\n{alias} = {task.name}\nclass Solution:\n    def {task.name}({signature}):\n        return {alias}({parameters})\n"
        payload = {"sample": fixture["sample"], "code": adapted, "test_count": task.test_count}
        return self.sandbox(payload, 7 * task.test_count + 30,
                            {"grader.py": (CACHE / "lcb-grader.py").read_text()})

    def reference(self, task) -> None:
        return None

    def health_check(self):
        probe = self.sandbox({
            "sample": {"input_output": json.dumps({"inputs": ["1"], "outputs": ["1"], "fn_name": "probe"})},
            "code": "class Solution:\n    def probe(self, x):\n        return x\n", "test_count": 1}, 15,
            {"grader.py": (CACHE / "lcb-grader.py").read_text()})
        if probe.passed is not True:
            raise RuntimeError("official LiveCodeBench grader health check failed")

    def prepare_worker(self, payload):
        return runpy.run_path(str(Path(payload["directory"]) / "grader.py"))["run_test"]

    def execute(self, payload, grader) -> Verdict:
        import numpy as np
        outcomes, metadata = grader(payload["sample"], test=payload["code"], timeout=6)
        outcomes = [r.item(0) if isinstance(r, np.ndarray) else r for r in outcomes]
        return Verdict(len(outcomes) == payload["test_count"] and all(r > 0 for r in outcomes),
                       None if all(r > 0 for r in outcomes) else json.dumps(metadata, default=str), False,
                       tests_passed=int(sum(r > 0 for r in outcomes)), tests_total=payload["test_count"])


BENCHMARKS = {benchmark.key: benchmark for benchmark in (HumanEvalPlus, MBPPPlus, LiveCodeBench)}
