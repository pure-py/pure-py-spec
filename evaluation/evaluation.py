import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import gzip
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
import warnings

import evaluation_sandbox


ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache/evaluation"
CHECKER_VERSION = "0.22.3"
CHECKER_SHA = "cd59f9e8656d2b617954caaf60bdb89d91ccc9cbee830d63977e8abf8a857c27"
HARNESS_SHA = "b7cb6a8a69807bb868150a61742e25d7bb5328bbe01d514471b6ec43c9fa9ed2"
CONDITIONS = ("python", "purepy")
OUTPUT_FORMAT_VERSION = "tagged-code-v1"
BENCHMARKS = {"humaneval": "HumanEval", "humaneval-plus": "HumanEval+", "mbpp-plus": "MBPP+",
              "livecodebench": "LiveCodeBench"}
EVALPLUS = ("humaneval-plus", "mbpp-plus")
SIMPLE_TYPES = {"int", "float", "bool", "str", "object"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


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


def load_rows(manifest):
    path = download(manifest["url"], CACHE / manifest["url"].rsplit("/", 1)[1], manifest["sha256"])
    with gzip.open(path, "rt") as source:
        rows = {row["task_id"]: row for row in map(json.loads, source)}
    if len(rows) != manifest["total_problems"]:
        raise RuntimeError(f"{manifest['benchmark']} benchmark size changed")
    return rows


def load_problems(benchmark, limit=None, difficulty=None, all_problems=False):
    if benchmark == "livecodebench":
        import livecodebench as lcb
        lcb.prepare(set())
        data = json.loads(lcb.TASKS.read_text())
        download("https://raw.githubusercontent.com/LiveCodeBench/LiveCodeBench/"
                 + lcb.HARNESS_REVISION + "/lcb_runner/evaluation/testing_util.py",
                 CACHE / "lcb-grader.py", HARNESS_SHA)
        problems = {k: {**v, "typed_interface": True} for k, v in data["tasks"].items()
                    if not difficulty or v["difficulty"] == difficulty}
        manifest = {**data["manifest"], "selection_sha256": sha(lcb.TASKS.read_bytes()),
                    "total_problems": 1055, "selected_problems": len(problems),
                    "scope": "Typed call-based subset of release_v6; 1055 release problems in total."}
        chosen = dict(list(problems.items())[:limit])
        lcb.prepare(set(chosen))
        for task_id, task in chosen.items():
            if sha(lcb.case_path(task_id).read_bytes()) != task["tests_sha256"]:
                raise RuntimeError("LiveCodeBench test fixture checksum mismatch")
    else:
        manifest = json.loads((ROOT / f"benchmarks/{benchmark}.json").read_text())
        rows = load_rows(manifest)
        task_ids = list(rows) if all_problems or not manifest.get("task_ids") else manifest["task_ids"]
        problems = {}
        for task_id in task_ids:
            row = rows[task_id]
            if benchmark == "mbpp-plus":
                signature, typed = function_signature(row["canonical_solution"], row["entry_point"])
            else:
                signature, typed = function_signature(row["prompt"], row["entry_point"])
            if benchmark == "humaneval":
                official = row
            else:
                reference = row["canonical_solution"] if benchmark == "mbpp-plus" else row["prompt"] + row["canonical_solution"]
                inputs = [list(group.values()) if isinstance(group, dict) else group
                          for group in (row["base_input"], row["plus_input"])]
                official = {"reference": reference, "inputs": inputs[0] + inputs[1], "atol": row["atol"]}
            problems[task_id] = {"name": row["entry_point"], "question": row["prompt"], "signature": signature,
                                 "typed_interface": typed, "official": official}
        manifest = {**manifest, "selected_problems": len(problems),
                    "typed_interfaces": sum(p["typed_interface"] for p in problems.values())}
        chosen = dict(list(problems.items())[:limit])
    return chosen, {**manifest, "evaluated_problems": len(chosen),
                    "evaluated_typed_interfaces": sum(p["typed_interface"] for p in chosen.values())}


def output_instruction(condition):
    language = "PurePy" if condition == "purepy" else "Python"
    return (f"Output only the complete {language} source code inside <{condition}>...</{condition}> tags. "
            "Use exactly one pair of these tags. Do not include explanations or any text outside the tags. "
            "Do not include Markdown fences, comments, a test runner or example calls.")


def prompt(task, condition):
    common = ("Preserve the required function name, parameters, return behaviour and input domain. "
              "Include necessary imports and helpers.\n\n")
    definition = (ROOT / "prompts/purepy-v0.22.3.md").read_text() if condition == "purepy" else ""
    return (("Solve this task in PurePy.\n" if condition == "purepy" else "Solve this task in Python.\n")
            + common + definition + "\nTask:\n" + task["question"]
            + "\n\nRequired function interface:\n" + task["signature"]
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


def check(code):
    if not code.strip():
        return {"passed": None, "error": "no generated code to check", "tooling_error": False}
    with tempfile.TemporaryDirectory(prefix="purepy-check-") as directory:
        path = Path(directory) / "solution.py"
        path.write_text(code)
        cli = Path(sys.executable).parent / "purepy"
        try:
            result = subprocess.run([str(cli), "--check", "--module", str(path)],
                                    capture_output=True, text=True, timeout=30,
                                    env={"PATH": "/usr/bin:/bin"})
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"passed": None, "error": type(error).__name__, "tooling_error": True}
        diagnostic = (result.stdout + result.stderr).strip().replace(str(path), "solution.py")
        tooling = result.returncode not in (0, 1, 2, 3, 4) or "Traceback (most recent call last)" in diagnostic
        verdict = {"passed": None if tooling else result.returncode == 0 and bool(code.strip()),
                   "error": diagnostic if result.returncode or not code.strip() else None,
                   "exit_code": result.returncode, "tooling_error": tooling,
                   "command": ["purepy", "--check", "--module", "solution.py"]}
        if not code.strip():
            verdict["error"] = "no generated code"
        if verdict["passed"] is False:
            verdict["failure_mode"] = failure_category(code, verdict["error"], result.returncode)
        return verdict


def official_tests(code, task, benchmark):
    if not code.strip():
        return {"passed": None, "error": "no generated code to test", "tooling_error": False}
    try:
        tree = ast.parse(code)
        if not any(isinstance(n, ast.FunctionDef) and n.name == task["name"] for n in tree.body):
            return {"passed": False, "error": "required top-level function is missing", "tooling_error": False}
    except SyntaxError as error:
        return {"passed": False, "error": str(error), "tooling_error": False}
    if benchmark == "humaneval":
        problem = task["official"]
        program = problem["prompt"] + "\n" + code + "\n" + problem["test"] + "\ncheck(" + task["name"] + ")\n"
        return evaluation_sandbox.run({"benchmark": "HumanEval", "program": program}, 3)
    if benchmark in EVALPLUS:
        official = task["official"]
        return evaluation_sandbox.run({"benchmark": "EvalPlus", "reference": official["reference"], "candidate": code,
                                       "name": task["name"], "inputs": official["inputs"], "atol": official["atol"]}, 60)
    import livecodebench as lcb
    fixture = json.loads(lcb.case_path(task["task_id"]).read_text())
    alias = "_lcb_core_" + sha(task["task_id"].encode())[:12]
    parameters = ", ".join(task["parameters"])
    signature = "self" + (", " + parameters if parameters else "")
    adapted = code + f"\n{alias} = {task['name']}\nclass Solution:\n    def {task['name']}({signature}):\n        return {alias}({parameters})\n"
    payload = {"benchmark": "LiveCodeBench", "sample": fixture["sample"], "code": adapted,
               "test_count": task["test_count"], "grader_source": (CACHE / "lcb-grader.py").read_text()}
    return evaluation_sandbox.run(payload, 7 * task["test_count"] + 30)


def validate_backend(benchmark):
    if sys.version_info[:2] != (3, 12) or version("purepy") != CHECKER_VERSION:
        raise RuntimeError("the pipeline requires Python 3.12 and the pinned PurePy wheel")
    accepted = check("def probe(x: int) -> int:\n    return x\n")
    rejected = check("def probe(x: int) -> int:\n    for i in range(0, x):\n        pass\n    return x\n")
    if accepted["passed"] is not True or rejected["passed"] is not False:
        raise RuntimeError("checker health check failed")
    program = "def probe():\n    return 1\nassert probe() == 1\n"
    sandbox = evaluation_sandbox.run({"benchmark": "HumanEval", "program": program}, 3)
    if sandbox["passed"] is not True:
        raise RuntimeError("sandbox health check failed: " + str(sandbox["error"]))
    isolation = evaluation_sandbox.run({"benchmark": "HumanEval", "program":
        "import os, socket\nassert 'ANTHROPIC_API_KEY' not in os.environ\n"
        "assert 'DEEPSEEK_API_KEY' not in os.environ\n"
        "try:\n    socket.create_connection(('1.1.1.1', 443), timeout=1)\n"
        "except OSError:\n    pass\nelse:\n    raise AssertionError('network was accessible')\n"
        + f"assert not os.access({str(ROOT / 'pyproject.toml')!r}, os.R_OK)\n"}, 3)
    if isolation["passed"] is not True:
        raise RuntimeError("sandbox isolation check failed")
    if benchmark in EVALPLUS:
        identity = "def probe(x):\n    return x\n"
        probe = {"benchmark": "EvalPlus", "reference": identity, "candidate": identity, "name": "probe",
                 "inputs": [[1], [2.5], [[1, 2]]], "atol": 0}
        wrong = {**probe, "candidate": "def probe(x):\n    return None\n"}
        if (evaluation_sandbox.run(probe, 10)["passed"] is not True
                or evaluation_sandbox.run(wrong, 10)["passed"] is not False):
            raise RuntimeError("EvalPlus test runner health check failed")
    if benchmark == "livecodebench":
        probe = evaluation_sandbox.run({"benchmark": "LiveCodeBench",
            "grader_source": (CACHE / "lcb-grader.py").read_text(),
            "sample": {"input_output": json.dumps({"inputs": ["1"], "outputs": ["1"], "fn_name": "probe"})},
            "code": "class Solution:\n    def probe(self, x):\n        return x\n", "test_count": 1}, 15)
        if probe["passed"] is not True:
            raise RuntimeError("official LiveCodeBench grader health check failed")


def repair_messages(messages, attempt):
    return [*messages, {"role": "assistant", "content": attempt["raw_response"]},
            {"role": "user", "content":
             "The PurePy v0.22.3 checker rejected this source:\n" + attempt["checker"]["error"]
             + "\nCorrect the source while preserving the task interface and behaviour. "
             + output_instruction("purepy")}]


def pack_solution(attempts, initial_prompt):
    for current, following in zip(attempts, attempts[1:]):
        if current["checker"]["passed"] is not False:
            continue
        mode = current["checker"].get("failure_mode", {})
        next_mode = following["checker"].get("failure_mode", {})
        current["next_round_clears_reported_feature"] = (
            True if following["checker"]["passed"] is True else
            False if following["checker"]["passed"] is False
            and (mode.get("category"), mode.get("restriction"))
            == (next_mode.get("category"), next_mode.get("restriction")) else None)
    final = attempts[-1]
    return {"code": final["code"], "checker": final["checker"], "official_tests": final["official_tests"],
            "generation": final["generation"], "prompt": initial_prompt, "attempts": attempts,
            "output_format": final.get("output_format"),
            "rejections": sum(a["checker"]["passed"] is False for a in attempts),
            "rounds_to_acceptance": next((a["round"] for a in attempts if a["checker"]["passed"] is True), None)}


def attempt_solution(args, task, condition, persist=None):
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
        answer.update(round=round_index, messages=messages,
                      prompt_sha256=sha(json.dumps(messages, sort_keys=True).encode()))
        answer["checker"] = {"passed": None, "error": "awaiting checker", "tooling_error": False}
        answer["official_tests"] = {"passed": None, "error": "awaiting tests", "tooling_error": False}
        attempts.append(answer)
        if persist:
            persist(pack_solution(attempts, initial_prompt))
        if answer["generation"]["status"] != "complete" or not answer["code"]:
            reason = ("generation " + answer["generation"]["status"]
                      if answer["generation"]["status"] != "complete" else
                      "output format: " + answer["output_format"]["status"])
            for metric in ("checker", "official_tests"):
                answer[metric] = {"passed": None, "error": "not evaluated because " + reason,
                                  "tooling_error": False}
        else:
            answer["checker"] = check(answer["code"])
            answer["official_tests"] = official_tests(answer["code"], task, args.benchmark)
        if persist:
            persist(pack_solution(attempts, initial_prompt))
        if (answer["generation"]["status"] != "complete" or answer["checker"]["passed"] is not False
                or answer["checker"]["tooling_error"] or answer["official_tests"]["tooling_error"]):
            break
        messages = repair_messages(messages, answer)
    return pack_solution(attempts, initial_prompt)


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
                "checker_accepts": sum(a["checker"]["passed"] is True for a in attempts),
                "tests_pass": sum(a["official_tests"]["passed"] is True for a in attempts),
                "joint_pass": sum(a["checker"]["passed"] is True and a["official_tests"]["passed"] is True for a in attempts),
                "checker_unknown": sum(a["checker"]["passed"] is None for a in attempts),
                "tests_unknown": sum(a["official_tests"]["passed"] is None for a in attempts),
                "format_compliant": sum((a.get("output_format") or {}).get("compliant") is True for a in attempts),
                "format_noncompliant": sum((a.get("output_format") or {}).get("compliant") is False for a in attempts),
                "format_unknown": sum((a.get("output_format") or {}).get("compliant") is None for a in attempts),
                "format_status": dict(Counter((a.get("output_format") or {}).get("status", "unrecorded")
                                              for a in attempts)),
                "generation_status": dict(Counter(a["generation"]["status"] for a in attempts))}
        failures = [a["checker"].get("failure_mode", {}) for s in solutions for a in s["attempts"]
                    if a["checker"]["passed"] is False]
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
        accepted = [(q, p) for q, p in pairs if q["checker"]["passed"] is True]
        count = len(accepted)
        purepy_pass = sum(q["official_tests"]["passed"] is True for q, p in accepted)
        python_pass = sum(p["official_tests"]["passed"] is True for q, p in accepted)
        unknown = sum(q["official_tests"]["passed"] is None or p["official_tests"]["passed"] is None
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
        (folder / f"{condition}.round-{attempt['round']}.py").write_text(attempt["code"] + "\n")


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
    data = json.loads(source.read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    plot(data, summarize(data), [destination])
    print(f"Figure: {destination}", flush=True)


def report(path):
    data = json.loads(path.read_text())
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
            values = [task_id, condition, last["generation"]["status"],
                      (first.get("output_format") or {}).get("status", "unrecorded"),
                      (last.get("output_format") or {}).get("status", "unrecorded"), first["checker"]["passed"],
                      last["checker"]["passed"], first["official_tests"]["passed"],
                      last["official_tests"]["passed"], solution["rounds_to_acceptance"]]
            lines.append("| " + " | ".join(map(str, values)) + " |")
    lines.extend(["", "## Rejection Details", "",
                  "The checker reports one diagnostic per run, so the next round's diagnostic may name a different feature.", "",
                  "| Task | Condition | Round | Category | Restriction | Next Round Clears Feature | Diagnostic |",
                  "|---|---|---:|---|---|---|---|"])
    for task_id, task in data["tasks"].items():
        for condition in CONDITIONS:
            for attempt in task.get(condition, {}).get("attempts", []):
                if attempt["checker"]["passed"] is not False:
                    continue
                mode = attempt["checker"]["failure_mode"]
                values = [task_id, condition, attempt["round"], mode["category"], mode["restriction"],
                          attempt.get("next_round_clears_reported_feature"), attempt["checker"]["error"]]
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
        data = json.loads(path.read_text())
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
    problems, manifest = load_problems(args.benchmark, args.limit, args.difficulty, getattr(args, "all_problems", False))
    if not problems:
        raise RuntimeError("the selection contains no problems")
    validate_backend(args.benchmark)
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
    data = {"benchmark": BENCHMARKS[args.benchmark],
            "model": args.model, "manifest": manifest, "tasks": {},
            "protocol": {"checker_version": CHECKER_VERSION, "wheel_sha256": CHECKER_SHA,
                         "definition_sha256": sha((ROOT / "prompts/purepy-v0.22.3.md").read_bytes()),
                         "prompt_version": OUTPUT_FORMAT_VERSION, "output_format": OUTPUT_FORMAT_VERSION,
                         "python": sys.version.split()[0], "platform": sys.platform,
                         "provider": args.provider, "base_url": args.base_url, "max_tokens": args.max_tokens,
                         "model_size_b": getattr(args, "model_size", None),
                         "repair_rounds": args.repair_rounds, "feedback": "checker diagnostics only",
                         "automatic_retries": 0, "started_at": datetime.now(timezone.utc).isoformat()},
            "status": "running"}
    save(path, data)
    failed = False
    try:
        for task_id, task in problems.items():
            task = {**task, "task_id": task_id}
            data["tasks"][task_id] = {k: v for k, v in task.items() if k != "official"}
            for condition in CONDITIONS:
                def persist(solution):
                    data["tasks"][task_id][condition] = solution
                    save(path, data)
                    export_code(path, task_id, condition, solution)

                solution = attempt_solution(args, task, condition, persist)
                data["tasks"][task_id][condition] = solution
                save(path, data)
                print(f"{task_id} {condition}: checker={solution['checker']['passed']} "
                      f"tests={solution['official_tests']['passed']} status={solution['generation']['status']}", flush=True)
                if any(a["checker"]["tooling_error"] or a["official_tests"]["tooling_error"]
                       or a["generation"]["status"] == "api_error" for a in solution["attempts"]):
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
    try:
        run(args)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
