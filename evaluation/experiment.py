"""Generate or evaluate paired solutions, using one model-named JSON file."""

import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "Qwen2.5-Coder-7B-Instruct.json"
CHECKER = ROOT / ".cache/pure-py-spec"
DATASET = ROOT / ".cache/human-eval/data/HumanEval.jsonl.gz"
CHECKER_COMMIT = "68486f84cf80cbc6a4a954dc5d3953951e37b9e3"
DATASET_SHA256 = "b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef"

# Runs inside the OS sandbox; the official test text is supplied unchanged.
TEST_RUNNER = '''
import contextlib, io, json, resource, signal, sys, traceback
payload = json.load(sys.stdin)
resource.setrlimit(resource.RLIMIT_CPU, (3, 4))
resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
def timeout(signum, frame):
    raise TimeoutError("official tests exceeded 3 seconds")
signal.signal(signal.SIGALRM, timeout)
signal.setitimer(signal.ITIMER_REAL, 3)
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        exec(compile(payload["program"], "solution_and_official_tests.py", "exec"), {})
    result = {"passed": True, "error": None}
except BaseException:
    result = {"passed": False, "error": traceback.format_exc().strip()}
finally:
    signal.setitimer(signal.ITIMER_REAL, 0)
print(json.dumps(result))
'''


def save(path, data):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def not_run(message):
    return {"passed": None, "error": message}


def run_checker(code):
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "solution.py"
        source.write_text(code)
        try:
            result = subprocess.run(
                [str(CHECKER / ".venv/bin/python"), str(CHECKER / "src/check_module.py"), str(source)],
                capture_output=True, text=True, timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return not_run(f"checker tooling error: {error}")
        diagnostic = (result.stdout + result.stderr).strip().replace(str(source), "solution.py")
        if result.returncode == 0:
            return {"passed": True, "error": None}
        if result.returncode in (1, 2, 3, 4) and "Traceback (most recent call last)" not in diagnostic:
            return {"passed": False, "error": diagnostic}
        return not_run(f"checker tooling error: {diagnostic}")


def sandbox_profile(directory):
    runtime = Path(sys.executable).resolve().parent.parent
    return f'''(version 1)
    (deny default)
    (allow process-exec (literal {json.dumps(str(Path(sys.executable).resolve()))}))
    (allow sysctl-read)
    (allow mach-lookup)
    (allow signal (target self))
    (allow file-read-metadata)
    (allow file-read*
      (require-all (require-not (subpath "/Users")) (require-not (subpath "/Volumes"))
                   (require-not (subpath "/private/var/folders")))
      (subpath {json.dumps(str(runtime))}) (subpath {json.dumps(directory)}))
    (allow file-write* (subpath {json.dumps(directory)}) (literal "/dev/null"))
    '''


def run_official_tests(code, problem):
    try:
        definitions = ast.parse(code).body
        if not any(isinstance(node, ast.FunctionDef) and node.name == problem["entry_point"] for node in definitions):
            return {"passed": False, "error": "generated source does not define the required function"}
    except SyntaxError as error:
        return {"passed": False, "error": str(error)}
    # HumanEval supplies imports/helpers through its original prompt. Full generated
    # source follows that prompt and overrides its unfinished target definition.
    program = problem["prompt"] + "\n" + code + "\n" + problem["test"] + "\ncheck(" + problem["entry_point"] + ")\n"
    with tempfile.TemporaryDirectory() as directory:
        python = str(Path(sys.executable).resolve())
        command = ["/usr/bin/sandbox-exec", "-p", sandbox_profile(directory), python, "-I", "-c", TEST_RUNNER]
        try:
            result = subprocess.run(command, input=json.dumps({"program": program}), capture_output=True,
                                    text=True, cwd=directory, timeout=8, env={"PATH": "/usr/bin:/bin"})
        except subprocess.TimeoutExpired:
            return {"passed": False, "error": "official tests timed out"}
        except OSError as error:
            return not_run(f"sandbox tooling error: {error}")
        if result.returncode != 0:
            return not_run(f"sandbox worker error: {result.stderr.strip() or result.returncode}")
        try:
            verdict = json.loads(result.stdout)
            assert isinstance(verdict["passed"], bool)
            return verdict
        except (ValueError, KeyError, AssertionError):
            return not_run("sandbox worker did not return a test verdict")


def evaluate(path, data):
    revision = subprocess.check_output(["git", "-C", str(CHECKER), "rev-parse", "HEAD"], text=True).strip()
    if revision != CHECKER_COMMIT or hashlib.sha256(DATASET.read_bytes()).hexdigest() != DATASET_SHA256:
        raise RuntimeError("checker revision or official dataset does not match the fixed experiment")
    with gzip.open(DATASET, "rt") as source:
        problems = {task["task_id"]: task for task in map(json.loads, source)}
    # Refuse to execute candidates if the sandbox cannot run an innocuous probe.
    probe = run_official_tests("def sandbox_probe():\n    return 1\n", {
        "prompt": "", "entry_point": "sandbox_probe", "test": "def check(candidate):\n    assert candidate() == 1\n"})
    if probe["passed"] is not True:
        raise RuntimeError(f"sandbox unavailable: {probe['error']}")
    for task_id, task in data["tasks"].items():
        for condition in ("python", "purepy"):
            solution = task[condition]
            solution["checker"] = run_checker(solution["code"])
            solution["official_tests"] = run_official_tests(solution["code"], problems[task_id])
            save(path, data)
            print(f"{task_id} {condition}: checker={solution['checker']['passed']} tests={solution['official_tests']['passed']}", flush=True)


def generate(path, data, api_url):
    definition = (ROOT / "skills/purepy-definition/references/definition.md").read_text()
    for task_id, task in data["tasks"].items():
        for condition in ("python", "purepy"):
            if task[condition]["code"]:
                continue  # Preserve first outputs; never silently regenerate them.
            prompt = (ROOT / f"prompts/{condition}.md").read_text()
            prompt = prompt.replace("{{problem_statement}}", task["question"])
            prompt = prompt.replace("{{function_signature}}", task["signature"])
            prompt = prompt.replace("{{purepy_definition}}", definition)
            request = urllib.request.Request(api_url.rstrip("/") + "/chat/completions", headers={"Content-Type": "application/json"},
                data=json.dumps({"model": data["model"], "messages": [{"role": "user", "content": prompt}],
                                 "temperature": 0, "top_p": 1, "seed": 0, "max_tokens": 4096, "n": 1}).encode())
            with urllib.request.urlopen(request, timeout=300) as response:
                choice = json.load(response)["choices"][0]
            raw = choice["message"]["content"] or ""
            code = raw.strip()
            lines = code.splitlines()
            if len(lines) >= 3 and lines[0] in ("```python", "```") and lines[-1] == "```":
                code = "\n".join(lines[1:-1])
            task[condition] = {"code": code, "checker": not_run("not run"), "official_tests": not_run("not run")}
            if choice["finish_reason"] != "stop" or not code:
                task[condition]["generation_error"] = f"finish_reason={choice['finish_reason']}; empty={not code}"
            save(path, data)
            print(f"{task_id} {condition}: saved", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["evaluate", "generate"])
    parser.add_argument("--file", type=Path, default=RESULTS)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/v1")
    args = parser.parse_args()
    data = json.loads(args.file.read_text())
    if args.action == "evaluate":
        evaluate(args.file, data)
    else:
        generate(args.file, data, args.api_url)


if __name__ == "__main__":
    main()
