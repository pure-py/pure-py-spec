import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from evaluation_benchmarks import BENCHMARKS, HumanEval, Problem, Verdict, encode_verdict


ROOT = Path(__file__).resolve().parent
CHECKER_VERSION = "0.22.3"
CHECKER_SHA = "cd59f9e8656d2b617954caaf60bdb89d91ccc9cbee830d63977e8abf8a857c27"
CONDITIONS = ("python", "purepy")
OUTPUT_FORMAT_VERSION = "tagged-code-v1"
ACCEPTS_ANY_ANSWER = ("are_equivalent",)


class Unrecorded(Enum):
    VALUE = "unrecorded"


@dataclass
class Attempt:
    round: int
    code: str
    generation: dict[str, object]
    messages: list[dict[str, str]]
    prompt_sha256: str
    checker: Verdict = field(default_factory=lambda: Verdict(None, "awaiting checker", False))
    official_tests: Verdict = field(default_factory=lambda: Verdict(None, "awaiting tests", False))
    raw_response: str | Unrecorded = Unrecorded.VALUE
    output_format: dict[str, object] | None | Unrecorded = Unrecorded.VALUE
    next_round_clears_reported_feature: bool | None | Unrecorded = Unrecorded.VALUE

    @classmethod
    def from_dict(cls, record):
        return cls(**{**record, "checker": Verdict(**record["checker"]),
                      "official_tests": Verdict(**record["official_tests"])})

    def to_dict(self):
        self.validate()
        return {f.name: getattr(self, f.name) for f in fields(self)
                if getattr(self, f.name) is not Unrecorded.VALUE}

    def validate(self, *, finished=False):
        if type(self.round) is not int or self.round < 0:
            raise RuntimeError("attempt rounds must be nonnegative integers")
        evaluable = self.generation["status"] == "complete" and bool(self.code.strip())
        for name, verdict in (("checker", self.checker), ("official tests", self.official_tests)):
            if verdict.passed is not None and type(verdict.passed) is not bool:
                raise RuntimeError(f"{name} verdict must be true, false or unknown")
            if verdict.tooling_error and verdict.passed is not None:
                raise RuntimeError(f"{name} tooling errors must have unknown verdicts")
            if not evaluable and verdict.passed is not None:
                raise RuntimeError("unevaluated answers must have unknown verdicts")
            if finished and evaluable and verdict.passed is None and not verdict.tooling_error:
                raise RuntimeError(f"{name} verdict is still pending")
        if self.checker.passed is not None:
            expected = (0,) if self.checker.passed else (1, 2, 3, 4)
            if type(self.checker.exit_code) is not int or self.checker.exit_code not in expected:
                raise RuntimeError("checker verdict requires a matching completed checker exit status")

    @property
    def repairable(self):
        return (self.generation["status"] == "complete" and self.checker.passed is False
                and not self.checker.tooling_error and not self.official_tests.tooling_error)

    @property
    def format_status(self):
        return self.output_format.get("status", "unrecorded") if isinstance(self.output_format, dict) else "unrecorded"

    @property
    def format_compliant(self):
        return self.output_format.get("compliant") if isinstance(self.output_format, dict) else None


def encode_result(value):
    return value.to_dict() if isinstance(value, Attempt) else encode_verdict(value)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=encode_result) + "\n")
    temporary.replace(path)


def read_result(path):
    data = json.loads(path.read_text())
    for task in data["tasks"].values():
        for condition in CONDITIONS:
            if condition not in task:
                continue
            solution = task[condition]
            for metric in ("checker", "official_tests"):
                solution[metric] = Verdict(**solution[metric])
            solution["attempts"] = [Attempt.from_dict(record) for record in solution["attempts"]]
    return data


def output_instruction(condition):
    language = "PurePy" if condition == "purepy" else "Python"
    return (f"Output only the complete {language} source code inside <{condition}>...</{condition}> tags. "
            "Use exactly one pair of these tags. Do not include explanations or any text outside the tags. "
            "Do not include Markdown fences, comments, a test runner or example calls.")


def prompt(task: Problem, condition):
    common = ("Preserve the required function name, parameters, return behaviour and input domain. "
              "Include necessary imports and helpers.\n\n")
    definition = (ROOT / "prompts/purepy-v0.22.3.md").read_text() if condition == "purepy" else ""
    return (("Solve this task in PurePy.\n" if condition == "purepy" else "Solve this task in Python.\n")
            + common + definition + "\nTask:\n" + task.question
            + "\n\nRequired function interface:\n" + task.signature
            + "\n\n" + output_instruction(condition))


def extract_code(raw, condition):
    opening, closing = f"<{condition}>", f"</{condition}>"
    tags = re.findall(r"</?(?:python|purepy)\b[^>]*>", raw)
    match = re.search(re.escape(opening) + r"(.*?)" + re.escape(closing), raw, re.DOTALL)
    code = ""
    if not tags:
        status, error = "missing_tags", f"expected {opening} and {closing}"
    elif tags != [opening, closing] or match is None:
        status, error = "invalid_tags", "expected exactly one complete pair of condition-matching tags"
    elif not match[1].strip():
        status, error = "empty_code", "tagged source is empty"
    elif re.search(r"^\s*```", match[1], re.MULTILINE):
        status, error = "markdown_fence", "Markdown fences inside source tags are prohibited"
    else:
        code = match[1].strip()
        outside = (raw[:match.start()] + raw[match.end():]).strip()
        status, error = ("outside_text", "text outside source tags") if outside else ("valid", None)
    return {"code": code, "output_format": {"version": OUTPUT_FORMAT_VERSION, "tag": condition,
            "status": status, "compliant": status == "valid", "error": error}}


def validate_api_url(base_url):
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.scheme not in ("http", "https"):
        raise RuntimeError("API URL must not include credentials, query parameters or fragments")
    if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("remote API connections require HTTPS")


def read_completion_stream(response):
    content = []
    result = {"choices": [{"message": {"content": ""}, "finish_reason": None}]}
    for line in response:
        if not line.startswith(b"data:"):
            continue
        event = line[5:].strip()
        if event == b"[DONE]":
            if result["choices"][0]["finish_reason"] is None or "usage" not in result:
                raise RuntimeError("API stream is missing its final verdict or token usage; not retried")
            result["choices"][0]["message"]["content"] = "".join(content)
            return result
        if not event:
            continue
        chunk = json.loads(event)
        if "error" in chunk:
            raise RuntimeError("API returned a streaming error; no automatic retry was made")
        for field in ("id", "model", "system_fingerprint"):
            if chunk.get(field) is not None:
                result[field] = chunk[field]
        if chunk.get("usage") is not None:
            result["usage"] = chunk["usage"]
        for choice in chunk.get("choices", []):
            if choice.get("index", 0) != 0:
                raise RuntimeError("expected exactly one generated answer")
            text = choice.get("delta", {}).get("content")
            if text:
                content.append(text)
            if choice.get("finish_reason") is not None:
                result["choices"][0]["finish_reason"] = choice["finish_reason"]
    raise RuntimeError("API stream disconnected before [DONE]; no automatic retry was made")


def request(base_url, provider, model, messages, max_tokens):
    validate_api_url(base_url)
    key_name = {"anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
                "openai": "OPENAI_API_KEY"}[provider]
    key = os.environ.get(key_name, "").strip()
    if not key and provider != "openai":
        raise RuntimeError(f"set {key_name} locally; do not put credentials in files")
    headers = {"Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if provider == "anthropic":
        if base_url.rstrip("/") != "https://api.anthropic.com/v1":
            raise RuntimeError("Anthropic credentials require the official API URL")
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        if os.getenv("ANTHROPIC_WORKSPACE_ID"):
            headers["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
        payload.update(thinking={"type": "adaptive"}, output_config={"effort": "high"})
        endpoint = "/messages"
    else:
        if provider == "deepseek" and base_url.rstrip("/") != "https://api.deepseek.com":
            raise RuntimeError("DeepSeek credentials require the official API URL")
        if key:
            headers["Authorization"] = "Bearer " + key
        if provider == "deepseek":
            payload.update(thinking={"type": "enabled"}, reasoning_effort="high",
                           stream=True, stream_options={"include_usage": True})
        else:
            payload.update(temperature=0, top_p=1, seed=0, n=1)
        endpoint = "/chat/completions"
    call = urllib.request.Request(base_url.rstrip("/") + endpoint, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(call, timeout=1800) as response:
            if payload.get("stream"):
                body = read_completion_stream(response)
            else:
                body = json.load(response)
    except urllib.error.HTTPError as error:
        return {"code": "", "generation": {"status": "api_error", "http_status": error.code,
                                              "error": f"API HTTP {error.code}"}}
    except (OSError, ValueError, RuntimeError) as error:
        return {"code": "", "generation": {"status": "api_error", "error": type(error).__name__}}
    if provider == "anthropic":
        raw = "".join(b["text"] for b in body["content"] if b["type"] == "text")
        stop = body["stop_reason"]
        complete = stop == "end_turn"
    else:
        if len(body.get("choices", [])) != 1:
            raise RuntimeError("expected exactly one model response")
        raw = body["choices"][0]["message"].get("content") or ""
        stop = body["choices"][0]["finish_reason"]
        complete = stop == "stop"
    return {"code": raw, "raw_response": raw,
            "generation": {"status": "complete" if complete and raw.strip() else "incomplete",
                           "stop_reason": stop, "response_id": body.get("id"),
                           "response_model": body.get("model"), "usage": body.get("usage", {})}}


def failure_category(code, diagnostic, exit_code):
    if not code.strip():
        return {"category": "no_output", "restriction": "no source produced"}
    lower = diagnostic.lower()
    if "parse error" in lower:
        return {"category": "syntax_or_format", "restriction": "invalid Python"}
    if "keyword arguments in a call other than a constructor" in lower:
        return {"category": "unsupported_feature", "restriction": "function keyword arguments"}
    rules = [("for loop", "loop"), ("while loop", "loop"), ("for statement", "loop"),
             ("while statement", "loop"), ("generator expression", "generator_expression"),
             ("item assignment", "mutation"), ("attribute assignment", "mutation"),
             ("augmented assignment", "mutation"), ("already assigned", "single_assignment"),
             ("never declared", "variable_declaration"), ("before its declaration", "variable_declaration"),
             ("unannotated", "type_annotation"), ("slicing", "slicing")]
    for text, restriction in rules:
        if text in lower:
            return {"category": "excluded_by_design", "restriction": restriction}
    if "unknown module" in lower or "is not defined" in lower or "has no member" in lower:
        return {"category": "library_or_name_resolution", "restriction": "unavailable or undefined name",
                "review_required": True}
    if "prohibited" in lower:
        return {"category": "syntax_restriction_review", "restriction": diagnostic.split(": ")[-1],
                "review_required": True}
    return {"category": "static_type_or_wellformedness", "restriction": "manual review required",
            "review_required": True, "exit_code": exit_code}


def check(code) -> Verdict:
    if not code.strip():
        return Verdict(None, "no generated code to check", False)
    with tempfile.TemporaryDirectory(prefix="purepy-check-") as directory:
        path = Path(directory) / "solution.py"
        path.write_text(code)
        cli = Path(sys.executable).parent / "purepy"
        try:
            result = subprocess.run([str(cli), "--check", "--module", str(path)],
                                    capture_output=True, text=True, timeout=30,
                                    env={"PATH": "/usr/bin:/bin"})
        except (OSError, subprocess.TimeoutExpired) as error:
            return Verdict(None, type(error).__name__, True)
        diagnostic = (result.stdout + result.stderr).strip().replace(str(path), "solution.py")
        tooling = result.returncode not in (0, 1, 2, 3, 4) or "Traceback (most recent call last)" in diagnostic
        passed = None if tooling else result.returncode == 0
        error = diagnostic if result.returncode else None
        return Verdict(passed, error, tooling, exit_code=result.returncode,
                       command=["purepy", "--check", "--module", "solution.py"],
                       failure_mode=failure_category(code, error, result.returncode) if passed is False else None)


def validate_backend(benchmark):
    if sys.version_info[:2] != (3, 12) or version("purepy") != CHECKER_VERSION:
        raise RuntimeError("the pipeline requires Python 3.12 and the pinned PurePy wheel")
    accepted = check("def probe(x: int) -> int:\n    return x\n")
    rejected = check("def probe(x: int) -> int:\n    for i in range(0, x):\n        pass\n    return x\n")
    if accepted.passed is not True or rejected.passed is not False:
        raise RuntimeError("checker health check failed")
    program = "def probe():\n    return 1\nassert probe() == 1\n"
    sandbox = HumanEval().sandbox({"program": program}, 3)
    if sandbox.passed is not True:
        raise RuntimeError("sandbox health check failed: " + str(sandbox.error))
    isolation = HumanEval().sandbox({"program":
        "import os, socket\nassert 'ANTHROPIC_API_KEY' not in os.environ\n"
        "assert 'DEEPSEEK_API_KEY' not in os.environ\n"
        "try:\n    socket.create_connection(('1.1.1.1', 443), timeout=1)\n"
        "except OSError:\n    pass\nelse:\n    raise AssertionError('network was accessible')\n"
        + f"assert not os.access({str(ROOT / 'pyproject.toml')!r}, os.R_OK)\n"}, 3)
    if isolation.passed is not True:
        raise RuntimeError("sandbox isolation check failed")
    benchmark.health_check()


def validate_problem(task: Problem, benchmark):
    reference = benchmark.reference(task)
    if reference is not None:
        verdict = benchmark.grade(reference, task)
        if verdict.passed is not True:
            raise RuntimeError(f"the reference solution of {task.task_id} fails its tests: {verdict.error}")
    wrong = benchmark.grade(f"def {task.name}(*args):\n    return None\n", task)
    if wrong.passed is not False and task.name not in ACCEPTS_ANY_ANSWER:
        raise RuntimeError(f"the tests of {task.task_id} accept an answer that returns None")


def validate_problems(problems, benchmark):
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        for outcome in pool.map(lambda task: validate_problem(task, benchmark), problems.values()):
            pass
    print(f"Validated the tests of {len(problems)} problems", flush=True)


def repair_messages(messages, attempt: Attempt):
    return [*messages, {"role": "assistant", "content": attempt.raw_response},
            {"role": "user", "content":
             "The PurePy v0.22.3 checker rejected this source:\n" + attempt.checker.error
             + "\nCorrect the source while preserving the task interface and behaviour. "
             + output_instruction("purepy")}]


def pack_solution(attempts: list[Attempt], initial_prompt, condition, repair_rounds, *, pending=False):
    if condition not in CONDITIONS or type(repair_rounds) is not int or repair_rounds < 0:
        raise RuntimeError("invalid condition or repair budget")
    budget = repair_rounds if condition == "purepy" else 0
    if not attempts or len(attempts) > budget + 1:
        raise RuntimeError("attempt history is empty or exceeds the repair budget")
    for index, attempt in enumerate(attempts):
        attempt.validate(finished=index < len(attempts) - 1 or not pending)
        if attempt.round != index:
            raise RuntimeError("attempt rounds must be consecutive, starting at zero")
        if index and not attempts[index - 1].repairable:
            raise RuntimeError("repair continued after acceptance or another stopping condition")
    if not pending and attempts[-1].repairable and len(attempts) < budget + 1:
        raise RuntimeError("repair stopped before acceptance or the repair limit")
    for current, following in zip(attempts, attempts[1:]):
        if current.checker.passed is not False:
            continue
        mode = current.checker.failure_mode or {}
        next_mode = following.checker.failure_mode or {}
        current.next_round_clears_reported_feature = (
            True if following.checker.passed is True else
            False if following.checker.passed is False
            and (mode.get("category"), mode.get("restriction"))
            == (next_mode.get("category"), next_mode.get("restriction")) else None)
    final = attempts[-1]
    return {"code": final.code, "checker": final.checker, "official_tests": final.official_tests,
            "generation": final.generation, "prompt": initial_prompt, "attempts": attempts,
            "output_format": None if final.output_format is Unrecorded.VALUE else final.output_format,
            "rejections": sum(a.checker.passed is False for a in attempts),
            "rounds_to_acceptance": next((a.round for a in attempts if a.checker.passed is True), None)}


def attempt_solution(args, task: Problem, condition, persist=None):
    initial_prompt = prompt(task, condition)
    messages = [{"role": "user", "content": initial_prompt}]
    attempts = []
    for round_index in range(1 + (args.repair_rounds if condition == "purepy" else 0)):
        answer = request(args.base_url, args.provider, args.model, messages, args.max_tokens)
        if answer["generation"]["status"] == "api_error":
            answer["output_format"] = {"version": OUTPUT_FORMAT_VERSION, "tag": condition,
                                       "status": "not_evaluated", "compliant": None,
                                       "error": "generation failed"}
        else:
            answer.update(extract_code(answer["raw_response"], condition))
        attempt = Attempt(**answer, round=round_index, messages=messages,
                          prompt_sha256=sha(json.dumps(messages, sort_keys=True).encode()))
        attempts.append(attempt)
        if persist:
            persist(pack_solution(attempts, initial_prompt, condition, args.repair_rounds, pending=True))
        if attempt.generation["status"] != "complete" or not attempt.code:
            reason = ("generation " + attempt.generation["status"]
                      if attempt.generation["status"] != "complete" else
                      "output format: " + attempt.format_status)
            attempt.checker = Verdict(None, "not evaluated because " + reason, False)
            attempt.official_tests = Verdict(None, "not evaluated because " + reason, False)
        else:
            attempt.checker = check(attempt.code)
            attempt.official_tests = args.benchmark.grade(attempt.code, task)
        attempt.validate(finished=True)
        if persist:
            persist(pack_solution(attempts, initial_prompt, condition, args.repair_rounds, pending=True))
        if not attempt.repairable:
            break
        messages = repair_messages(messages, attempt)
    return pack_solution(attempts, initial_prompt, condition, args.repair_rounds)


def summarize(data):
    summary = {"problems": len(data["tasks"]), "benchmark_total": data["manifest"]["total_problems"],
               "scope": data["manifest"]["scope"], "conditions": {}}
    for condition in CONDITIONS:
        solutions = [t[condition] for t in data["tasks"].values() if condition in t]
        rows = {}
        for stage in ("initial", "final"):
            attempts = [s["attempts"][0 if stage == "initial" else -1] for s in solutions]
            rows[stage] = {
                "outputs": len(attempts),
                "checker_accepts": sum(a.checker.passed is True for a in attempts),
                "tests_pass": sum(a.official_tests.passed is True for a in attempts),
                "joint_pass": sum(a.checker.passed is True and a.official_tests.passed is True for a in attempts),
                "checker_unknown": sum(a.checker.passed is None for a in attempts),
                "tests_unknown": sum(a.official_tests.passed is None for a in attempts),
                "format_compliant": sum(a.format_compliant is True for a in attempts),
                "format_noncompliant": sum(a.format_compliant is False for a in attempts),
                "format_unknown": sum(a.format_compliant is None for a in attempts),
                "format_status": dict(Counter(a.format_status for a in attempts)),
                "generation_status": dict(Counter(a.generation["status"] for a in attempts))}
        failures = [a.checker.failure_mode or {} for s in solutions for a in s["attempts"]
                    if a.checker.passed is False]
        rows["checker_rejections"] = dict(Counter(f.get("category", "unclassified") for f in failures))
        rows["rounds_to_acceptance"] = dict(Counter(str(s["rounds_to_acceptance"]) for s in solutions))
        summary["conditions"][condition] = rows
    n = max(1, summary["problems"])
    summary["rq3"] = {}
    for stage in ("initial", "final"):
        python = summary["conditions"]["python"][stage]
        purepy = summary["conditions"]["purepy"][stage]
        summary["rq3"][stage] = {
            "python_minus_purepy_tests_pp": (
                100 * (python["tests_pass"] - purepy["tests_pass"]) / n
                if python["outputs"] == purepy["outputs"] == n
                and not (python["tests_unknown"] or purepy["tests_unknown"]) else None),
            "python_tests_minus_valid_purepy_pp": (
                100 * (python["tests_pass"] - purepy["joint_pass"]) / n
                if python["outputs"] == purepy["outputs"] == n
                and not (python["tests_unknown"] or purepy["checker_unknown"] or purepy["tests_unknown"]) else None)}
    summary["rq3_accepted"] = {}
    for stage in ("initial", "final"):
        index = 0 if stage == "initial" else -1
        pairs = [(t["purepy"]["attempts"][index], t["python"]["attempts"][index])
                 for t in data["tasks"].values() if "purepy" in t and "python" in t]
        accepted = [(q, p) for q, p in pairs if q.checker.passed is True]
        count = len(accepted)
        purepy_pass = sum(q.official_tests.passed is True for q, p in accepted)
        python_pass = sum(p.official_tests.passed is True for q, p in accepted)
        unknown = sum(q.official_tests.passed is None or p.official_tests.passed is None
                      for q, p in accepted)
        known = count > 0 and not unknown
        summary["rq3_accepted"][stage] = {
            "problems": count, "purepy_tests_pass": purepy_pass, "python_tests_pass": python_pass,
            "tests_unknown": unknown,
            "purepy_rate_pct": 100 * purepy_pass / count if known else None,
            "python_rate_pct": 100 * python_pass / count if known else None,
            "python_minus_purepy_pp": 100 * (python_pass - purepy_pass) / count if known else None}
    return summary


def format_gap(value):
    return "unknown" if value is None else f"{value:.1f}"


def export_code(path, task_id, condition, solution):
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", task_id)
    folder = path.parent / "solutions" / path.stem / safe_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (condition + ".py")).write_text(solution["code"] + "\n")
    for attempt in solution["attempts"]:
        (folder / f"{condition}.round-{attempt.round}.py").write_text(attempt.code + "\n")


def plot(data, summary, destinations):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = max(1, summary["problems"])
    labels = ["Python initial", "PurePy initial", "PurePy repaired"]
    values = [summary["conditions"]["python"]["initial"], summary["conditions"]["purepy"]["initial"],
              summary["conditions"]["purepy"]["final"]]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for axis, metric, title in zip(axes, ["tests_pass", "joint_pass"],
                                   ["Official Tests", "Valid PurePy vs Python Tests"]):
        counts = [v[metric] for v in values]
        if metric == "joint_pass":
            counts[0] = values[0]["tests_pass"]
        unknown = [v["tests_unknown"] or v["outputs"] != summary["problems"]
                   or metric == "joint_pass" and i > 0 and v["checker_unknown"]
                   for i, v in enumerate(values)]
        bars = axis.bar(labels, [100 * c / n for c in counts], color=["#5b7386", "#d8973c", "#367c65"])
        for bar, missing in zip(bars, unknown):
            if missing:
                bar.set_hatch("//")
        axis.bar_label(bars, labels=[f"{c}/{summary['problems']} (incomplete)" if missing
                                    else f"{c}/{summary['problems']}" for c, missing in zip(counts, unknown)], padding=3)
        axis.set_ylim(0, 112)
        axis.set_ylabel("Passing Problems (%)")
        axis.set_title(title)
        axis.tick_params(axis="x", labelrotation=12)
    fig.suptitle(f"{data['model']} | {data['benchmark']} | {summary['problems']}/{summary['benchmark_total']} problems")
    for destination in destinations:
        fig.savefig(destination)
    plt.close(fig)


def figure(source, destination):
    data = read_result(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    plot(data, summarize(data), [destination])
    print(f"Figure: {destination}", flush=True)


def report(path):
    data = read_result(path)
    summary = summarize(data)
    data["summary"] = summary
    save(path, data)
    lines = [f"# {data['model']}", "", f"Benchmark: {data['benchmark']}",
             f"Problems: {summary['problems']} of {summary['benchmark_total']}",
             f"Typed interfaces: {data['manifest'].get('evaluated_typed_interfaces', 'unrecorded')} of {summary['problems']}",
             f"Scope: {summary['scope']}", f"PurePy checker: {data['protocol']['checker_version']}",
             f"Maximum checker-feedback repair rounds: {data['protocol']['repair_rounds']}", "",
             f"Output format: {data['protocol'].get('output_format', 'untagged')}", "",
             "| Condition | Stage | Checker Accepts | Official Tests Pass | Both Pass | Checker Unknown | Tests Unknown |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for condition, stages in summary["conditions"].items():
        for stage in ("initial", "final"):
            s = stages[stage]
            lines.append(f"| {condition} | {stage} | {s['checker_accepts']}/{s['outputs']} | "
                         f"{s['tests_pass']}/{s['outputs']} | {s['joint_pass']}/{s['outputs']} | "
                         f"{s['checker_unknown']} | {s['tests_unknown']} |")
    lines.extend(["", "Initial and repaired results are reported separately; Python answers receive no feedback.",
                  "Unknown verdicts come from API errors, truncated responses and format failures; "
                  "they count neither as passes nor as rejections.", "",
                  "## Output Format", "",
                  "| Condition | Stage | Compliant | Noncompliant | Unknown | Details |",
                  "|---|---|---:|---:|---:|---|"])
    for condition, stages in summary["conditions"].items():
        for stage in ("initial", "final"):
            s = stages[stage]
            lines.append(f"| {condition} | {stage} | {s['format_compliant']} | {s['format_noncompliant']} | "
                         f"{s['format_unknown']} | {json.dumps(s['format_status'], sort_keys=True)} |")
    lines.extend(["", "## Checker Rejections", ""])
    for condition, stages in summary["conditions"].items():
        lines.append(f"{condition}: {json.dumps(stages['checker_rejections'], sort_keys=True)}")
    lines.extend(["", "## RQ3", "",
                  "Positive values mean Python leads; negative values mean PurePy leads.", ""])
    for stage, gaps in summary["rq3"].items():
        lines.append(f"{stage}: Python minus PurePy official-test pass rate = "
                     f"{format_gap(gaps['python_minus_purepy_tests_pp'])} percentage points; "
                     f"Python tests minus valid PurePy = {format_gap(gaps['python_tests_minus_valid_purepy_pp'])} percentage points.")
    lines.extend(["", "On the problems whose PurePy answer the checker accepted, both conditions' official-test pass rates "
                  "measure the restrictions' effect on correctness.", ""])
    for stage, accepted in summary["rq3_accepted"].items():
        if not accepted["problems"]:
            lines.append(f"{stage}: no accepted PurePy answers.")
            continue
        lines.append(f"{stage}: {accepted['problems']} accepted problems; PurePy passes "
                     f"{accepted['purepy_tests_pass']}/{accepted['problems']} ({format_gap(accepted['purepy_rate_pct'])}%), "
                     f"Python passes {accepted['python_tests_pass']}/{accepted['problems']} ({format_gap(accepted['python_rate_pct'])}%); "
                     f"Python minus PurePy = {format_gap(accepted['python_minus_purepy_pp'])} percentage points.")
    lines.extend(["", "## Per-Solution Outcomes", "",
                  "| Task | Condition | Generation | Initial Format | Final Format | Initial Checker | Final Checker | Initial Tests | Final Tests | Repairs To Acceptance |",
                  "|---|---|---|---|---|---|---|---|---|---|"])
    for task_id, task in data["tasks"].items():
        for condition in CONDITIONS:
            if condition not in task:
                continue
            solution = task[condition]
            export_code(path, task_id, condition, solution)
            first, last = solution["attempts"][0], solution["attempts"][-1]
            values = [task_id, condition, last.generation["status"], first.format_status,
                      last.format_status, first.checker.passed, last.checker.passed, first.official_tests.passed,
                      last.official_tests.passed, solution["rounds_to_acceptance"]]
            lines.append("| " + " | ".join(map(str, values)) + " |")
    lines.extend(["", "## Rejection Details", "",
                  "The checker reports one diagnostic per run, so the next round's diagnostic may name a different feature.", "",
                  "| Task | Condition | Round | Category | Restriction | Next Round Clears Feature | Diagnostic |",
                  "|---|---|---:|---|---|---|---|"])
    for task_id, task in data["tasks"].items():
        for condition in CONDITIONS:
            for attempt in task.get(condition, {}).get("attempts", []):
                if attempt.checker.passed is not False:
                    continue
                mode = attempt.checker.failure_mode
                clears = attempt.next_round_clears_reported_feature
                values = [task_id, condition, attempt.round, mode["category"], mode["restriction"],
                          None if clears is Unrecorded.VALUE else clears, attempt.checker.error]
                lines.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in values) + " |")
    path.with_suffix(".md").write_text("\n".join(lines) + "\n")
    plot(data, summary, [path.with_suffix(".pdf"), path.with_suffix(".svg")])
    latex = ("\\begin{figure}[t]\n\\centering\n\\includegraphics[width=\\linewidth]{"
             + path.with_suffix(".pdf").name + "}\n\\caption{PurePy evaluation on "
             + str(summary["problems"]) + " of " + str(summary["benchmark_total"])
             + " benchmark problems. Initial and checker-feedback repaired outcomes are reported separately.}\n"
             "\\label{fig:purepy-evaluation}\n\\end{figure}\n")
    path.with_suffix(".tex").write_text(latex)
    print(f"Report: {path.with_suffix('.md')}", flush=True)
    return summary


def compare(paths, destination):
    destination = destination.resolve()
    if not destination.is_relative_to((ROOT / "results").resolve()):
        raise RuntimeError("comparison reports must be under results/")
    if destination.exists():
        raise RuntimeError("comparison already exists; choose a new destination")
    groups = {}
    for path in paths:
        data = read_result(path)
        protocol = data["protocol"]
        identity = {"benchmark": data["benchmark"], "manifest": data["manifest"],
                    "task_ids": sorted(data["tasks"]),
                    "prompts": {task_id: {c: sha(task[c]["prompt"].encode()) for c in CONDITIONS}
                                for task_id, task in data["tasks"].items()},
                    "checker_version": protocol["checker_version"], "wheel_sha256": protocol["wheel_sha256"],
                    "definition_sha256": protocol["definition_sha256"], "repair_rounds": protocol["repair_rounds"],
                    "prompt_version": protocol.get("prompt_version", "code-only-v1"),
                    "output_format": protocol.get("output_format", "untagged"),
                    "platform": protocol["platform"], "python": protocol["python"]}
        key = sha(json.dumps(identity, sort_keys=True).encode())[:16]
        group = groups.setdefault(key, {"protocol": identity, "models": []})
        group["models"].append({"model": data["model"], "model_size_b": protocol.get("model_size_b"),
                                "provider": protocol["provider"], "max_tokens": protocol["max_tokens"],
                                "status": data["status"], "source": str(path), "summary": summarize(data)})
    save(destination, {"groups": groups,
                       "question": "Does the Python-PurePy gap shrink as models become more capable?",
                       "note": "Groups match benchmark, tasks, prompts, checker, repair budget and platform; "
                               "provider settings and token budgets are listed per model."})
    lines = ["# RQ3 Cross-Model Comparison", "",
             "Python-PurePy gaps per model, for runs with matched tasks and protocol. Positive values mean Python leads.", ""]
    for key, group in groups.items():
        lines.extend([f"## Matched Protocol {key}", "",
                      "| Model | Size (B) | Stage | Python Tests | PurePy Tests | Valid PurePy | Test Gap (pp) | Validity Gap (pp) "
                      "| Accepted | PurePy Pass On Accepted | Python Pass On Accepted | Gap On Accepted (pp) | Status |",
                      "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"])
        for model in group["models"]:
            for stage in ("initial", "final"):
                summary = model["summary"]
                p, q = summary["conditions"]["python"][stage], summary["conditions"]["purepy"][stage]
                gaps = summary["rq3"][stage]
                accepted = summary["rq3_accepted"][stage]
                lines.append(f"| {model['model']} | {model['model_size_b']} | {stage} | {p['tests_pass']}/{summary['problems']} | "
                             f"{q['tests_pass']}/{summary['problems']} | {q['joint_pass']}/{summary['problems']} | "
                             f"{format_gap(gaps['python_minus_purepy_tests_pp'])} | "
                             f"{format_gap(gaps['python_tests_minus_valid_purepy_pp'])} | "
                             f"{accepted['problems']} | {accepted['purepy_tests_pass']}/{accepted['problems']} | "
                             f"{accepted['python_tests_pass']}/{accepted['problems']} | "
                             f"{format_gap(accepted['python_minus_purepy_pp'])} | {model['status']} |")
    destination.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(f"Comparison: {destination}", flush=True)


def run(args):
    problems, manifest = args.benchmark.load(args.limit, args.difficulty, getattr(args, "all_problems", False))
    if not problems:
        raise RuntimeError("the selection contains no problems")
    validate_backend(args.benchmark)
    validate_problems(problems, args.benchmark)
    if not args.base_url:
        args.base_url = {"openai": "http://127.0.0.1:11434/v1", "deepseek": "https://api.deepseek.com",
                         "anthropic": "https://api.anthropic.com/v1"}[args.provider]
    validate_api_url(args.base_url)
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.model)
    path = args.output or ROOT / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") / (name + ".json")
    path = path.resolve()
    if path.exists():
        raise RuntimeError("results already exist; choose a new output file to preserve the original run")
    if not path.is_relative_to((ROOT / "results").resolve()):
        raise RuntimeError("new results must be under results/")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write("{}\n")
    data = {"benchmark": args.benchmark.name,
            "model": args.model, "manifest": manifest, "tasks": {},
            "protocol": {"checker_version": CHECKER_VERSION, "wheel_sha256": CHECKER_SHA,
                         "definition_sha256": sha((ROOT / "prompts/purepy-v0.22.3.md").read_bytes()),
                         "prompt_version": OUTPUT_FORMAT_VERSION, "output_format": OUTPUT_FORMAT_VERSION,
                         "python": sys.version.split()[0], "platform": sys.platform,
                         "provider": args.provider, "base_url": args.base_url, "max_tokens": args.max_tokens,
                         "model_size_b": getattr(args, "model_size", None),
                         "repair_rounds": args.repair_rounds, "feedback": "checker diagnostics only",
                         "problem_checks": "reference solution passes; an answer returning None fails",
                         "automatic_retries": 0, "started_at": datetime.now(timezone.utc).isoformat()},
            "status": "running"}
    save(path, data)
    failed = False
    try:
        for task in problems.values():
            task_id = task.task_id
            data["tasks"][task_id] = task.to_record()
            for condition in CONDITIONS:
                def persist(solution):
                    data["tasks"][task_id][condition] = solution
                    save(path, data)
                    export_code(path, task_id, condition, solution)

                solution = attempt_solution(args, task, condition, persist)
                data["tasks"][task_id][condition] = solution
                save(path, data)
                print(f"{task_id} {condition}: checker={solution['checker'].passed} "
                      f"tests={solution['official_tests'].passed} status={solution['generation']['status']}", flush=True)
                if any(a.checker.tooling_error or a.official_tests.tooling_error
                       or a.generation["status"] == "api_error" for a in solution["attempts"]):
                    failed = True
    except BaseException as error:
        data["status"] = "interrupted"
        data["error_type"] = type(error).__name__
        save(path, data)
        raise
    data["status"] = "infrastructure_failed" if failed else "complete"
    data["protocol"]["finished_at"] = datetime.now(timezone.utc).isoformat()
    save(path, data)
    summary = report(path)
    print(f"Results: {path}", flush=True)
    for condition, stages in summary["conditions"].items():
        for stage in ("initial", "final"):
            s = stages[stage]
            print(f"{condition} {stage}: checker accepts {s['checker_accepts']} of {s['outputs']}, "
                  f"tests pass {s['tests_pass']} of {s['outputs']}", flush=True)
    if failed:
        raise RuntimeError("API, checker or test infrastructure failed; inspect the saved report")
    return path


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    execution = sub.add_parser("run")
    execution.add_argument("--benchmark", choices=list(BENCHMARKS), default="humaneval")
    execution.add_argument("--all-problems", action="store_true", help="every problem of the benchmark instead of the frozen selection")
    execution.add_argument("--model", default="qwen2.5-coder:0.5b")
    execution.add_argument("--provider", choices=["openai", "anthropic", "deepseek"], default="openai")
    execution.add_argument("--base-url")
    execution.add_argument("--max-tokens", type=int, default=2048)
    execution.add_argument("--repair-rounds", type=int, default=0)
    execution.add_argument("--limit", type=int)
    execution.add_argument("--difficulty", choices=["medium", "hard"])
    execution.add_argument("--output", type=Path)
    execution.add_argument("--model-size", type=float, help="known parameter count in billions; leave hosted-model sizes unknown")
    reporting = sub.add_parser("report")
    reporting.add_argument("file", type=Path)
    plotting = sub.add_parser("figure")
    plotting.add_argument("file", type=Path)
    plotting.add_argument("--output", required=True, type=Path)
    comparison = sub.add_parser("compare")
    comparison.add_argument("files", nargs="+", type=Path)
    comparison.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "report":
        report(args.file)
        return
    if args.action == "figure":
        figure(args.file, args.output)
        return
    if args.action == "compare":
        compare(args.files, args.output)
        return
    if args.max_tokens < 1 or args.repair_rounds < 0 or args.limit is not None and args.limit < 1:
        parser.error("token/selection limits must be positive and repair rounds must be nonnegative")
    if args.model_size is not None and args.model_size <= 0:
        parser.error("--model-size must be positive when supplied")
    if args.difficulty and args.benchmark != "livecodebench":
        parser.error("difficulty filtering applies only to LiveCodeBench")
    if args.all_problems and args.benchmark == "livecodebench":
        parser.error("LiveCodeBench runs its frozen selection only")
    args.benchmark = BENCHMARKS[args.benchmark]()
    try:
        run(args)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
