"""Generate or evaluate paired solutions, using one model-named JSON file."""

import argparse
import ast
import getpass
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "Qwen2.5-Coder-7B-Instruct.json"
CHECKER = ROOT / ".cache/pure-py-checker-v0.19.0"
DATASET = ROOT / ".cache/human-eval/data/HumanEval.jsonl.gz"
CHECKER_COMMIT = "68486f84cf80cbc6a4a954dc5d3953951e37b9e3"
DATASET_SHA256 = "b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef"

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
    path.parent.mkdir(parents=True, exist_ok=True)
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
                [str(Path(sys.executable).resolve()), str(CHECKER / "src/check_module.py"), str(source)],
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


def sandbox_profile(directory, read_paths=()):
    directory = str(Path(directory).resolve())
    runtime = Path(sys.executable).resolve().parent.parent
    extra = " ".join(f"(literal {json.dumps(str(path.resolve()))})" for path in read_paths)
    return f'''(version 1)
    (deny default)
    (allow process-exec (subpath {json.dumps(str(runtime))}) (literal {json.dumps(str(Path(sys.executable).resolve()))}))
    (allow sysctl-read)
    (allow mach-lookup)
    (allow signal (target self))
    (allow file-read-metadata)
    (allow file-read*
      (require-all (require-not (subpath "/Users")) (require-not (subpath "/Volumes"))
                   (require-not (subpath "/private/var/folders")))
      (subpath {json.dumps(str(runtime))}) (subpath {json.dumps(directory)}) {extra})
    (allow file-write* (subpath {json.dumps(directory)}) (literal "/dev/null"))
    '''


def run_official_tests(code, problem):
    try:
        definitions = ast.parse(code).body
        if not any(isinstance(node, ast.FunctionDef) and node.name == problem["entry_point"] for node in definitions):
            return {"passed": False, "error": "generated source does not define the required function"}
    except SyntaxError as error:
        return {"passed": False, "error": str(error)}
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
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("use Python 3.12 for the pinned checker and official tests")
    revision = subprocess.check_output(["git", "-C", str(CHECKER), "rev-parse", "HEAD"], text=True).strip()
    if revision != CHECKER_COMMIT:
        raise RuntimeError("checker revision does not match the fixed experiment")
    lcb = data.get("benchmark") == "LiveCodeBench"
    if lcb:
        import livecodebench
        harness_revision = subprocess.check_output(["git", "-C", str(livecodebench.HARNESS.parents[2]), "rev-parse", "HEAD"], text=True).strip()
        if harness_revision != livecodebench.HARNESS_REVISION:
            raise RuntimeError("LiveCodeBench official grader revision changed")
    else:
        if hashlib.sha256(DATASET.read_bytes()).hexdigest() != DATASET_SHA256:
            raise RuntimeError("official HumanEval dataset changed")
        with gzip.open(DATASET, "rt") as source:
            problems = {task["task_id"]: task for task in map(json.loads, source)}
    probe = run_official_tests("def sandbox_probe():\n    return 1\n", {
        "prompt": "", "entry_point": "sandbox_probe", "test": "def check(candidate):\n    assert candidate() == 1\n"})
    if probe["passed"] is not True:
        raise RuntimeError(f"sandbox unavailable: {probe['error']}")
    for task_id, task in data["tasks"].items():
        for condition in ("python", "purepy"):
            solution = task[condition]
            if solution["code"]:
                solution["checker"] = run_checker(solution["code"])
                solution["official_tests"] = (livecodebench.evaluate_solution(solution["code"], task_id, task)
                                               if lcb else run_official_tests(solution["code"], problems[task_id]))
            else:
                solution["checker"] = not_run("no generated code to check")
                solution["official_tests"] = not_run("no generated code to test")
            save(path, data)
            print(f"{task_id} {condition}: checker={solution['checker']['passed']} tests={solution['official_tests']['passed']}", flush=True)


def make_prompt(task, condition):
    definition = (ROOT / "skills/purepy-definition/references/definition.md").read_text()
    prompt = (ROOT / f"prompts/{condition}.md").read_text()
    return (prompt.replace("{{problem_statement}}", task["question"])
            .replace("{{function_signature}}", task["signature"])
            .replace("{{purepy_definition}}", definition))


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


def api_json(url, payload=None, headers=None):
    idle_timeout = 1800 if payload is not None else 30
    request = urllib.request.Request(
        url, headers={"Content-Type": "application/json", **(headers or {})},
        data=None if payload is None else json.dumps(payload).encode())
    try:
        with urllib.request.urlopen(request, timeout=idle_timeout) as response:
            return read_completion_stream(response) if payload and payload.get("stream") else json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"API HTTP {error.code}; check credentials, model access and balance") from None
    except urllib.error.URLError:
        raise RuntimeError("API connection failed; no automatic retry was made") from None
    except TimeoutError:
        raise RuntimeError(f"API connection was idle for {idle_timeout} seconds; no automatic retry was made") from None


def anthropic_headers(key):
    headers = {"Authorization": "Bearer " + key, "anthropic-version": "2023-06-01"}
    if os.environ.get("ANTHROPIC_WORKSPACE_ID"):
        headers["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
    return headers


def request_settings(provider, max_tokens):
    if provider == "anthropic":
        return {"max_tokens": max_tokens, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "high"}}
    if provider == "deepseek":
        if not 1 <= max_tokens <= 393216:
            raise ValueError("DeepSeek max_tokens must be between 1 and 393216; an unlimited value is unsupported")
        settings = {"max_tokens": max_tokens, "thinking": {"type": "enabled"},
                    "reasoning_effort": "high"}
        if max_tokens > 16384:
            settings.update(stream=True, stream_options={"include_usage": True})
        return settings
    return {"temperature": 0, "top_p": 1, "seed": 0, "max_tokens": max_tokens, "n": 1}


def experiment_settings(data, provider, api_url, max_tokens):
    prompts = [(task_id, condition, make_prompt(task, condition))
               for task_id, task in data["tasks"].items() for condition in ("python", "purepy")]
    settings = {"provider": provider, "api_url": api_url,
            "checker_commit": CHECKER_COMMIT, "dataset_sha256": DATASET_SHA256,
            "prompts_sha256": hashlib.sha256(json.dumps(prompts, ensure_ascii=False).encode()).hexdigest(),
            "request_settings": request_settings(provider, max_tokens),
            "samples_per_condition": 1, "repair_rounds": 0, "automatic_retries": 0}
    if data.get("benchmark") == "LiveCodeBench":
        settings["benchmark"] = "LiveCodeBench"
        settings["selection_sha256"] = hashlib.sha256((ROOT / "livecodebench/tasks.json").read_bytes()).hexdigest()
    return settings


def prepare_results(path, model, benchmark="humaneval"):
    if path.exists():
        data = json.loads(path.read_text())
        if model and data["model"] != model:
            raise RuntimeError("result file belongs to a different model; refusing to overwrite it")
        return data
    if not model:
        raise RuntimeError("a new result file requires --model")
    source = ROOT / "livecodebench/tasks.json" if benchmark == "livecodebench" else RESULTS
    baseline = json.loads(source.read_text())
    tasks = {}
    for task_id, task in baseline["tasks"].items():
        fields = tuple(task) if benchmark == "livecodebench" else ("name", "question", "signature")
        tasks[task_id] = {field: task[field] for field in fields}
        for condition in ("python", "purepy"):
            tasks[task_id][condition] = {"code": "", "checker": not_run("not run"),
                                       "official_tests": not_run("not run")}
    result = {"model": model, "tasks": tasks}
    if benchmark == "livecodebench":
        result.update(benchmark="LiveCodeBench", manifest=baseline["manifest"])
    return result


def generate(path, data, api_url, provider="openai", key=None, max_tokens=4096, frozen_prompt=None):
    settings = experiment_settings(data, provider, api_url, max_tokens)
    if "experiment" in data and data["experiment"] != settings:
        raise RuntimeError("prompts or generation settings changed; use a separate result file")
    pending = [(task_id, condition) for task_id, task in data["tasks"].items()
               for condition in ("python", "purepy")
               if not task[condition]["code"] and "generation" not in task[condition]]
    if not pending:
        print("No unattempted outputs; existing answers and failed attempts were left unchanged.")
        return
    if frozen_prompt is not None and len(pending) != 1:
        raise RuntimeError("a frozen prompt must target exactly one unattempted output")
    if provider == "anthropic":
        if api_url != "https://api.anthropic.com/v1":
            raise RuntimeError("Anthropic credentials are sent only to the official HTTPS API")
        if not key:
            raise RuntimeError("set ANTHROPIC_API_KEY or use --ask-key; never put the key in this file")
        info = api_json(api_url + "/models/" + data["model"], headers=anthropic_headers(key))
        if info["id"] != data["model"]:
            raise RuntimeError(f"use the resolved model ID: {info['id']}")
    if provider == "deepseek":
        if api_url != "https://api.deepseek.com":
            raise RuntimeError("DeepSeek credentials are sent only to the official HTTPS API")
        if not key:
            raise RuntimeError("set DEEPSEEK_API_KEY or use --ask-key; never put the key in this file")
        info = api_json(api_url + "/models", headers={"Authorization": "Bearer " + key})
        if not any(model["id"] == data["model"] for model in info["data"]):
            raise RuntimeError("requested model is not available for this DeepSeek account")
    data["experiment"] = settings
    save(path, data)
    for task_id, task in data["tasks"].items():
        for condition in ("python", "purepy"):
            if (task_id, condition) not in pending:
                continue
            prompt = frozen_prompt if frozen_prompt is not None else make_prompt(task, condition)
            payload = {"model": data["model"], "messages": [{"role": "user", "content": prompt}],
                       **settings["request_settings"]}
            task[condition]["generation"] = {"status": "in_progress"}
            save(path, data)
            try:
                if provider == "anthropic":
                    response = api_json(api_url + "/messages", payload, anthropic_headers(key))
                    raw = "".join(block["text"] for block in response["content"] if block["type"] == "text")
                    stop = response["stop_reason"]
                    complete = stop == "end_turn"
                else:
                    headers = {"Authorization": "Bearer " + key} if provider == "deepseek" else None
                    response = api_json(api_url + "/chat/completions", payload, headers)
                    choice = response["choices"][0]
                    raw = choice["message"]["content"] or ""
                    stop = choice["finish_reason"]
                    complete = stop == "stop"
            except Exception as error:
                task[condition]["generation"] = {"status": "api_error", "error": str(error)}
                save(path, data)
                raise
            code = raw.strip()
            lines = code.splitlines()
            if len(lines) >= 3 and lines[0] in ("```python", "```") and lines[-1] == "```":
                code = "\n".join(lines[1:-1])
            task[condition] = {"code": code, "checker": not_run("not run"), "official_tests": not_run("not run")}
            task[condition]["generation"] = {
                "status": "complete" if complete and code else "incomplete", "stop_reason": stop,
                "response_id": response.get("id"), "response_model": response.get("model"),
                "system_fingerprint": response.get("system_fingerprint"),
                "usage": response.get("usage", {})}
            if frozen_prompt is not None:
                task[condition]["generation"]["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
            save(path, data)
            print(f"{task_id} {condition}: saved", flush=True)


def gpu_generate(path, data, model_path, revision, max_tokens, max_model_len=16384,
                 generate_callback=None, server_python=None):
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("GPU generation must run inside a Slurm allocation, not on a login node")
    model_path = model_path.resolve()
    if model_path.name != revision:
        raise RuntimeError("model snapshot directory must match the pinned revision")
    index = json.loads((model_path / "model.safetensors.index.json").read_text())
    for shard in set(index["weight_map"].values()):
        if not (model_path / shard).is_file():
            raise RuntimeError(f"model snapshot is incomplete: {shard}")
    if data.get("runtime", {}).get("model_revision", revision) != revision:
        raise RuntimeError("refusing to mix model revisions in one result file")
    from importlib.metadata import version
    saved_port = 0
    if generate_callback and data.get("experiment"):
        from urllib.parse import urlsplit
        previous = urlsplit(data["experiment"]["api_url"])
        if previous.scheme != "http" or previous.hostname != "127.0.0.1" or previous.port is None:
            raise RuntimeError("cannot reuse an unexpected inference endpoint")
        saved_port = previous.port
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", saved_port))
        port = reservation.getsockname()[1]
    api_url = f"http://127.0.0.1:{port}/v1"
    interpreter = str(server_python) if server_python else sys.executable
    command = [interpreter, "-m", "vllm.entrypoints.openai.api_server", "--model", str(model_path),
               "--served-model-name", data["model"], "--host", "127.0.0.1", "--port", str(port),
               "--dtype", "bfloat16", "--tensor-parallel-size", "1", "--max-model-len", str(max_model_len),
               "--max-num-seqs", "2", "--gpu-memory-utilization", "0.85", "--generation-config", "vllm",
               "--seed", "0", "--enforce-eager"]
    if server_python:
        runtime = json.loads(subprocess.check_output([interpreter, "-c",
            "import json, sys; from importlib.metadata import version; "
            "print(json.dumps({'python_version':sys.version,'packages':{n:version(n) for n in ('vllm','torch','transformers')}}))"], text=True))
    else:
        runtime = {"python_version": sys.version,
                   "packages": {name: version(name) for name in ("vllm", "torch", "transformers")}}
    if generate_callback and data.get("runtime"):
        data.setdefault("runtime_history", []).append(data["runtime"])
    data["runtime"] = {"model_revision": revision, "model_path": str(model_path),
                       "job_id": os.environ["SLURM_JOB_ID"], **runtime,
                       "server_command": command}
    save(path, data)
    log_folder = ROOT / ".cache" / ("slurm-" + os.environ["SLURM_JOB_ID"])
    log_folder.mkdir(parents=True, exist_ok=True)
    with (log_folder / "vllm.log").open("a") as log:
        server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 900
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"vLLM exited before startup; see {log_folder / 'vllm.log'}")
                try:
                    with urllib.request.urlopen(api_url + "/models", timeout=5) as response:
                        models = json.load(response)
                    if not any(item["id"] == data["model"] for item in models["data"]):
                        raise RuntimeError("unexpected model on the local API port")
                    break
                except urllib.error.URLError:
                    if time.monotonic() > deadline:
                        raise RuntimeError("vLLM startup timed out") from None
                    time.sleep(2)
            if generate_callback:
                generate_callback(path, data, api_url, max_tokens)
            else:
                generate(path, data, api_url, max_tokens=max_tokens)
        finally:
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGTERM)
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["evaluate", "generate", "run", "gpu"], help="run generates then evaluates; gpu generates on a Slurm GPU")
    parser.add_argument("--file", type=Path, help="default: model name.json, or the existing Qwen result")
    parser.add_argument("--model", help="exact API model ID; creates a separate result for the same frozen tasks")
    parser.add_argument("--benchmark", choices=["humaneval", "livecodebench"], default="humaneval")
    parser.add_argument("--provider", choices=["openai", "anthropic", "deepseek"], default="openai")
    parser.add_argument("--api-url")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="total output cap, including thinking; DeepSeek currently supports up to 393216")
    parser.add_argument("--model-path", type=Path, help="gpu: complete cached model snapshot")
    parser.add_argument("--model-revision", help="gpu: pinned Hugging Face commit")
    parser.add_argument("--ask-key", action="store_true", help="enter a key locally with hidden input; never saved")
    args = parser.parse_args()
    folder = ROOT / "livecodebench" if args.benchmark == "livecodebench" else ROOT
    path = args.file or (folder / (args.model.split("/")[-1] + ".json") if args.model else RESULTS)
    if args.action == "evaluate" and not path.exists():
        parser.error("result file does not exist; generate answers before evaluating")
    data = prepare_results(path, args.model, args.benchmark)
    if args.max_tokens <= 0:
        parser.error("--max-tokens must be positive")
    if args.action == "gpu":
        if not args.model_path or not args.model_revision:
            parser.error("gpu requires --model-path and --model-revision")
        gpu_generate(path, data, args.model_path, args.model_revision, args.max_tokens,
                     32768 if args.benchmark == "livecodebench" else 16384)
    if args.action in ("generate", "run"):
        urls = {"anthropic": "https://api.anthropic.com/v1", "deepseek": "https://api.deepseek.com",
                "openai": "http://127.0.0.1:8000/v1"}
        api_url = (args.api_url or urls[args.provider]).rstrip("/")
        key_env = {"anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}.get(args.provider)
        if args.ask_key and key_env is None:
            parser.error("--ask-key is supported for anthropic and deepseek")
        key = (getpass.getpass(f"{args.provider} API key (hidden, not saved): ").strip() if args.ask_key
               else os.environ.get(key_env) if key_env else None)
        generate(path, data, api_url, args.provider, key, args.max_tokens)
    if args.action in ("evaluate", "run"):
        evaluate(path, data)


if __name__ == "__main__":
    main()
