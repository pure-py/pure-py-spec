"""Harbor orchestration for the existing, one-shot PurePy experiment protocol."""

import argparse
import asyncio
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import getpass
import gzip
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

os.environ["HARBOR_TELEMETRY"] = "0"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
sys.modules.setdefault("harbor_runner", sys.modules[__name__])

from filelock import FileLock, Timeout as LockTimeout
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.environments.capabilities import EnvironmentCapabilities
from harbor.job import Job
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import AgentConfig, EnvironmentConfig, TaskConfig, VerifierConfig
from harbor.models.verifier.result import VerifierResult
from harbor.verifier.base import BaseVerifier

import experiment as legacy


ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache/harbor"
JOBS = CACHE / "jobs"
EXPORTS = ROOT / "harbor/results"
HARBOR_VERSION = "0.24.0"
CONDITIONS = ("python", "purepy")
API_URLS = {"anthropic": "https://api.anthropic.com/v1", "deepseek": "https://api.deepseek.com",
            "openai": "http://127.0.0.1:8000/v1"}
_API_KEY = None
_PROBLEMS = None


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def benchmark(data):
    return "livecodebench" if data.get("benchmark") == "LiveCodeBench" else "humaneval"


def lock_for(path, purpose="write"):
    folder = CACHE / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    return FileLock(str(folder / (digest(str(path.resolve()))[:24] + f"-{purpose}.lock")),
                    timeout=30 if purpose == "write" else 0)


def protect_output(path):
    originals = {p.resolve() for p in source_files()}
    if path.resolve() in originals:
        raise RuntimeError("the original experiment files are read-only during migration; choose a new output path")


def update_answer(path, task_id, condition, solution):
    with lock_for(path):
        data = json.loads(path.read_text())
        data["tasks"][task_id][condition] = deepcopy(solution)
        legacy.save(path, data)


def validate_backend(kind):
    global _PROBLEMS
    if sys.platform != "darwin" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("verification requires the pinned macOS/Python 3.12 backend; use --generation-only on a GPU node")
    revision = subprocess.check_output(["git", "-C", str(legacy.CHECKER), "rev-parse", "HEAD"], text=True).strip()
    if revision != legacy.CHECKER_COMMIT:
        raise RuntimeError("PurePy checker revision changed")
    if kind == "livecodebench":
        import livecodebench as lcb
        revision = subprocess.check_output(["git", "-C", str(lcb.HARNESS.parents[2]), "rev-parse", "HEAD"], text=True).strip()
        if revision != lcb.HARNESS_REVISION:
            raise RuntimeError("official LiveCodeBench grader revision changed")
    else:
        if digest(legacy.DATASET.read_bytes()) != legacy.DATASET_SHA256:
            raise RuntimeError("official HumanEval dataset changed")
        with gzip.open(legacy.DATASET, "rt") as source:
            _PROBLEMS = {p["task_id"]: p for p in map(json.loads, source)}
    probe = legacy.run_official_tests("def probe():\n    return 1\n", {
        "prompt": "", "entry_point": "probe", "test": "def check(f):\n    assert f() == 1\n"})
    if probe["passed"] is not True:
        raise RuntimeError(f"OS sandbox is unavailable: {probe['error']}")


class EvaluationFiles(BaseEnvironment):
    """File-only Harbor environment; untrusted code runs only in the legacy OS sandbox.

    This deliberately exposes no shell and is not a general-purpose agent sandbox.
    """

    @staticmethod
    def type():
        return "purepy-files"

    @property
    def capabilities(self):
        return EnvironmentCapabilities()

    def _validate_definition(self):
        marker = json.loads((self.environment_dir / "adapter.json").read_text())
        if marker != {"adapter": "purepy-files", "version": 1}:
            raise ValueError("unsupported task environment")

    def local(self, path):
        path = PurePosixPath(str(path))
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("environment paths must be absolute and contained")
        target = (self.root / str(path).lstrip("/")).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("environment path escapes its private workspace")
        return target

    async def start(self, force_build=False):
        self._temporary = tempfile.TemporaryDirectory(prefix="purepy-harbor-")
        self.root = Path(self._temporary.name).resolve()
        await self.ensure_dirs(["/app", "/logs/agent", "/logs/verifier", "/logs/artifacts"])

    async def stop(self, delete=True):
        self._temporary.cleanup()

    async def exec(self, command, **kwargs):
        raise RuntimeError("shell execution is disabled; use the PurePy one-shot agent and verifier")

    async def ensure_dirs(self, dirs, **kwargs):
        for path in dirs:
            self.local(path).mkdir(parents=True, exist_ok=True)
        return ExecResult(return_code=0)

    async def reset_dirs(self, *, remove_dirs, create_dirs, **kwargs):
        for path in remove_dirs:
            local = self.local(path)
            if local == self.root:
                raise ValueError("cannot remove the workspace root")
            if local.is_dir():
                shutil.rmtree(local)
            elif local.exists():
                local.unlink()
        return await self.ensure_dirs(create_dirs)

    async def empty_dirs(self, dirs, **kwargs):
        return await self.reset_dirs(remove_dirs=dirs, create_dirs=dirs)

    async def upload_file(self, source_path, target_path):
        target = self.local(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)

    async def download_file(self, source_path, target_path):
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.local(source_path), target)

    async def upload_dir(self, source_dir, target_dir):
        source = Path(source_dir)
        if any(p.is_symlink() for p in source.rglob("*")):
            raise ValueError("symbolic links are not supported")
        shutil.copytree(source, self.local(target_dir), dirs_exist_ok=True)

    async def download_dir(self, source_dir, target_dir):
        shutil.copytree(self.local(source_dir), target_dir, dirs_exist_ok=True)

    async def is_file(self, path, **kwargs):
        return self.local(path).is_file()

    async def is_dir(self, path, **kwargs):
        return self.local(path).is_dir()


class OneShotAgent(BaseAgent):
    @staticmethod
    def name():
        return "purepy-one-shot"

    def version(self):
        return "1"

    async def setup(self, environment):
        if not isinstance(environment, EvaluationFiles):
            raise TypeError("this agent requires EvaluationFiles")

    async def run(self, instruction, environment, context):
        record = json.loads((environment.environment_dir.parent / "record.json").read_text())
        if digest(instruction.encode()) != record["prompt_sha256"]:
            raise RuntimeError("Harbor changed the frozen prompt; refusing to generate")
        record["prompt"] = instruction
        if record["mode"] in ("replay", "follow"):
            solution = (await self.follow_one(record) if record["mode"] == "follow"
                        else deepcopy(record["solution"]))
            context.n_input_tokens = context.n_output_tokens = 0
            context.cost_usd = 0
        else:
            try:
                solution = await asyncio.to_thread(self.generate_one, record)
            except BaseException:
                current = json.loads(Path(record["output"]).read_text())
                solution = current["tasks"][record["task_id"]][record["condition"]]
                legacy.save(self.logs_dir / "answer.json", solution)
                raise
            usage = solution.get("generation", {}).get("usage", {})
            context.n_input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
            context.n_output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
            context.n_cache_tokens = usage.get("cache_read_input_tokens", usage.get("prompt_cache_hit_tokens"))
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        legacy.save(self.logs_dir / "answer.json", solution)
        (self.logs_dir / "solution.py").write_text(solution["code"])
        environment.answer = solution
        context.metadata = {"mode": record["mode"], "task_id": record["task_id"],
                            "condition": record["condition"], "original_generation": solution.get("generation")}

    async def follow_one(self, record):
        while True:
            source = json.loads(Path(record["source_path"]).read_text())
            task = source["tasks"][record["task_id"]]
            if (source["model"] != record["model"] or source.get("experiment") != record["source_experiment"]
                    or digest(legacy.make_prompt(task, record["condition"]).encode()) != record["prompt_sha256"]):
                raise RuntimeError("the legacy producer changed model, settings or prompt")
            solution = deepcopy(task[record["condition"]])
            status = solution.get("generation", {}).get("status")
            if solution["code"] or status not in (None, "pending", "in_progress"):
                return solution
            try:
                os.kill(record["source_pid"], 0)
            except ProcessLookupError:
                if status == "in_progress":
                    solution["generation"].update(status="interrupted_legacy",
                        error="legacy producer exited with an unresolved request; not retried")
                solution["checker"] = legacy.not_run("legacy producer exited without a saved answer")
                solution["official_tests"] = legacy.not_run("legacy producer exited without a saved answer")
                return solution
            await asyncio.sleep(5)

    def generate_one(self, record):
        path = Path(record["output"])
        task_id, condition = record["task_id"], record["condition"]
        with lock_for(path):
            data = json.loads(path.read_text())
            existing = data["tasks"][task_id][condition]
            if existing["code"] or "generation" in existing:
                return existing
            existing["generation"] = {"status": "in_progress", "harbor_trial": self.session_id}
            legacy.save(path, data)
        task = deepcopy(record["task"])
        for c in CONDITIONS:
            task[c] = {"code": "", "checker": legacy.not_run("not run"), "official_tests": legacy.not_run("not run")}
            if c != condition:
                task[c]["generation"] = {"status": "not_requested"}
        mini = {"model": record["model"], "tasks": {task_id: task}}
        if record["benchmark"] == "livecodebench":
            mini["benchmark"] = "LiveCodeBench"
        request_file = self.logs_dir / "request.json"
        try:
            legacy.generate(request_file, mini, record["api_url"], record["provider"], _API_KEY, record["max_tokens"],
                            frozen_prompt=record["prompt"])
        except BaseException as error:
            solution = mini["tasks"][task_id][condition]
            if "generation" not in solution:
                solution["generation"] = {"status": "api_error", "error": type(error).__name__}
            update_answer(path, task_id, condition, solution)
            raise
        solution = mini["tasks"][task_id][condition]
        update_answer(path, task_id, condition, solution)
        return solution


def check_solution(record, solution):
    if not solution["code"]:
        return {"checker": legacy.not_run("no generated code to check"),
                "official_tests": legacy.not_run("no generated code to test")}
    code = solution["code"]
    checker = legacy.run_checker(code)
    if record["benchmark"] == "livecodebench":
        import livecodebench as lcb
        tests = lcb.evaluate_solution(code, record["task_id"], record["task"])
    else:
        tests = legacy.run_official_tests(code, _PROBLEMS[record["task_id"]])
    return {"checker": checker, "official_tests": tests}


def rewards_for(solution):
    checker = solution["checker"]["passed"]
    tests = solution["official_tests"]["passed"]
    rewards = {"code_present": int(bool(solution["code"])),
               "checker_evaluated": int(isinstance(checker, bool)),
               "tests_evaluated": int(isinstance(tests, bool))}
    if isinstance(checker, bool):
        rewards["checker_passed"] = int(checker)
    if isinstance(tests, bool):
        rewards["official_tests_passed"] = int(tests)
    if isinstance(checker, bool) and isinstance(tests, bool):
        rewards["joint_passed"] = int(checker and tests)
    return rewards


class PurePyVerifier(BaseVerifier):
    def __init__(self, *, recheck=False, generation_only=False, **kwargs):
        super().__init__(**kwargs)
        self.recheck = recheck
        self.generation_only = generation_only

    async def verify(self):
        record = json.loads((self.task.task_dir / "record.json").read_text())
        solution = deepcopy(self.environment.answer)
        if not self.generation_only and (self.recheck or record["mode"] != "replay"):
            solution.update(await asyncio.to_thread(check_solution, record, solution))
        folder = self.trial_paths.verifier_dir
        folder.mkdir(parents=True, exist_ok=True)
        legacy.save(folder / "verdict.json", solution)
        rewards = rewards_for(solution)
        legacy.save(folder / "reward.json", rewards)
        if record["mode"] != "replay":
            update_answer(Path(record["output"]), record["task_id"], record["condition"], solution)
        return VerifierResult(rewards=rewards)


def task_name(task_id, condition):
    return task_id.lower().replace("/", "-") + "-" + condition


def materialize(data, source_sha, mode, *, recheck=False, limit=None, output=None, provider=None,
                api_url=None, max_tokens=None, generation_only=False, source_path=None, source_pid=None,
                difficulty=None):
    identity = digest({"adapter": "1.0-grouped", "source": source_sha, "mode": mode, "recheck": recheck, "limit": limit,
                       "generation_only": generation_only, "output": str(output),
                       "provider": provider, "api_url": api_url, "max_tokens": max_tokens,
                       **({"source_path": str(source_path), "source_pid": source_pid} if source_path else {}),
                       **({"difficulty": difficulty} if difficulty else {})})[:16]
    bundle = CACHE / "tasks" / identity
    selected = list(data["tasks"].items())[:limit]
    records = []
    for task_id, task in selected:
        if difficulty and task.get("difficulty") != difficulty:
            continue
        for condition in CONDITIONS:
            solution = task[condition]
            attempted = bool(solution["code"]) or "generation" in solution
            if mode == "replay" and (not attempted or solution.get("generation", {}).get("status") == "in_progress"):
                continue
            if mode == "generate" and attempted:
                continue
            name = task_name(task_id, condition)
            folder = bundle / name
            cached = folder / "record.json"
            if cached.exists():
                old = json.loads(cached.read_text())
                expected = {"task_id": task_id, "condition": condition, "model": data["model"],
                            "mode": mode, "task": task, "solution": solution}
                if any(old.get(key) != value for key, value in expected.items()):
                    raise RuntimeError("cached Harbor task inputs changed; refusing to rewrite a frozen bundle")
                records.append({"name": name, "task_id": task_id, "condition": condition, "path": str(folder)})
                continue
            (folder / "environment").mkdir(parents=True, exist_ok=True)
            (folder / "tests").mkdir(exist_ok=True)
            prompt = (solution.get("prompt") or legacy.make_prompt(task, condition)
                      if mode == "replay" else legacy.make_prompt(task, condition))
            record = {"task_id": task_id, "condition": condition, "benchmark": benchmark(data),
                      "model": data["model"], "mode": mode, "task": task, "solution": solution,
                      "prompt": prompt, "prompt_sha256": digest(prompt.encode()), "output": str(output) if output else None,
                      "provider": provider, "api_url": api_url, "max_tokens": max_tokens,
                      "source_path": str(source_path), "source_pid": source_pid,
                      "source_experiment": data.get("experiment")}
            legacy.save(folder / "record.json", record)
            legacy.save(folder / "environment/adapter.json", {"adapter": "purepy-files", "version": 1})
            (folder / "instruction.md").write_text(prompt)
            (folder / "task.toml").write_text(
                'version = "1.0"\n\n[metadata]\n' + f'task_id = {json.dumps(task_id)}\ncondition = {json.dumps(condition)}\n'
                + f'difficulty = {json.dumps(task.get("difficulty", "unspecified"))}\n'
                + '\n[verifier]\ntimeout_sec = 400\n\n[environment]\nbuild_timeout_sec = 30\n')
            (folder / "tests/test.sh").write_text(
                '#!/bin/sh\nexit 1\n')
            records.append({"name": name, "task_id": task_id, "condition": condition, "path": str(folder)})
    return identity, records


async def run_job(data, source_sha, mode, *, recheck=False, limit=None, output=None, provider=None,
                  api_url=None, max_tokens=None, generation_only=False, concurrency=1,
                  source_path=None, source_pid=None, difficulty=None):
    identity, records = materialize(data, source_sha, mode, recheck=recheck, limit=limit, output=output,
                                   provider=provider, api_url=api_url, max_tokens=max_tokens,
                                   generation_only=generation_only, source_path=source_path, source_pid=source_pid,
                                   difficulty=difficulty)
    if not records:
        print(f"{data['model']}: no eligible unattempted or completed outputs")
        if mode == "replay":
            destination = output or EXPORTS / benchmark(data) / (data["model"].split("/")[-1] + ".json")
            protect_output(destination)
            snapshot = deepcopy(data)
            snapshot["harbor"] = {"version": HARBOR_VERSION, "mode": "snapshot-only", "job": None,
                                  "source_sha256": source_sha, "trials_exported": 0,
                                  "note": "no settled attempts; existing in-flight requests were not restarted"}
            legacy.save(destination, snapshot)
        return None
    label = data["model"].split("/")[-1].lower()
    job_name = f"{mode}-{benchmark(data)}-{label}-{identity}"
    config = JobConfig(
        job_name=job_name, jobs_dir=JOBS, n_attempts=1, n_concurrent_trials=concurrency,
        quiet=True, retry={"max_retries": 0},
        environment=EnvironmentConfig(import_path="harbor_runner:EvaluationFiles"),
        verifier=VerifierConfig(import_path="harbor_runner:PurePyVerifier",
                                kwargs={"recheck": recheck, "generation_only": generation_only}),
        agents=[AgentConfig(import_path="harbor_runner:OneShotAgent", model_name=data["model"])],
        tasks=[TaskConfig(path=Path(r["path"]),
                          source=f"{benchmark(data)}-{data['tasks'][r['task_id']].get('difficulty', 'pilot')}-{r['condition']}")
               for r in records])
    job = await Job.create(config)
    manifest = {"source_sha256": source_sha, "mode": mode, "recheck": recheck,
                "generation_only": generation_only, "records": records, "source": data}
    legacy.save(job.job_dir / "purepy.json", manifest)
    if mode != "replay":
        current = json.loads(output.read_text())
        current["harbor"] = {"version": HARBOR_VERSION, "job": str(job.job_dir), "mode": mode,
                             "status": "running", "source_sha256": source_sha}
        legacy.save(output, current)
    print(f"Harbor job: {job.job_dir} ({len(records)} trials)", flush=True)
    await job.run()
    result = export_job(job.job_dir, output)
    print(f"Exported: {result}", flush=True)
    stats = json.loads((job.job_dir / "result.json").read_text())["stats"]
    if stats["n_errored_trials"]:
        raise RuntimeError(f"{stats['n_errored_trials']} Harbor trials had tooling/API errors; attempts were preserved, not retried")
    return job.job_dir


def export_job(job_dir, output=None):
    job_dir = Path(job_dir).resolve()
    manifest = json.loads((job_dir / "purepy.json").read_text())
    data = deepcopy(manifest["source"])
    if manifest["mode"] != "replay" and output and output.exists():
        data = json.loads(output.read_text())
    index = {r["path"]: r for r in manifest["records"]}
    found, mismatches = 0, []
    for config_file in job_dir.glob("*/config.json"):
        config = json.loads(config_file.read_text())
        record = index.get(str(Path(config["task"]["path"]).resolve()))
        if record is None:
            continue
        folder = config_file.parent
        answer = folder / "verifier/verdict.json"
        if not answer.exists():
            answer = folder / "agent/answer.json"
        if not answer.exists():
            continue
        solution = json.loads(answer.read_text())
        task_id, condition = record["task_id"], record["condition"]
        original = data["tasks"][task_id][condition]
        if manifest["mode"] == "replay" and solution["code"] != original["code"]:
            raise RuntimeError("replay changed the generated code")
        if manifest["recheck"]:
            for metric in ("checker", "official_tests"):
                old, new = original[metric]["passed"], solution[metric]["passed"]
                if isinstance(old, bool) and old != new:
                    mismatches.append({"task_id": task_id, "condition": condition,
                                       "metric": metric, "before": old, "after": new})
        data["tasks"][task_id][condition] = solution
        found += 1
    destination = output or EXPORTS / benchmark(data) / (data["model"].split("/")[-1] + ".json")
    protect_output(destination)
    reference = str(job_dir.relative_to(ROOT.resolve())) if job_dir.is_relative_to(ROOT.resolve()) else str(job_dir)
    data["harbor"] = {"version": HARBOR_VERSION, "job": reference,
                      "source_sha256": manifest["source_sha256"], "mode": manifest["mode"],
                      "rechecked": manifest["recheck"], "generation_only": manifest["generation_only"],
                      "trials_exported": found, "trials_expected": len(index), "parity_mismatches": mismatches,
                      "exported_at": datetime.now(timezone.utc).isoformat()}
    legacy.save(destination, data)
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} parity differences; original result files were not changed; see {destination}")
    if found != len(index):
        print(f"WARNING: {found}/{len(index)} answers exported; inspect Harbor trial errors", flush=True)
    return destination


def source_files():
    return sorted([*ROOT.glob("*.json"), *(ROOT / "livecodebench").glob("*.json")])


async def migrate(args):
    for path in args.file or source_files():
        raw = path.read_bytes()
        data = json.loads(raw)
        if "model" not in data:
            continue
        if args.verify and data.get("protocol", {}).get("checker_version", "0.19.0") != "0.19.0":
            raise RuntimeError("new-version results must use --recorded-only; do not recheck them with the legacy checker")
        if args.verify:
            validate_backend(benchmark(data))
        destination = args.output or EXPORTS / benchmark(data) / (data["model"].split("/")[-1] + ".json")
        if args.limit and args.output is None:
            destination = CACHE / "parity" / benchmark(data) / (data["model"].split("/")[-1] + ".json")
        try:
            with lock_for(destination, "run"):
                await run_job(data, digest(raw), "replay", recheck=args.verify, limit=args.limit,
                              output=destination, concurrency=args.concurrency)
        except LockTimeout:
            print(f"{data['model']}: an active Harbor job owns the export; skipped")


async def follow(args):
    source = args.file.resolve()
    raw = source.read_bytes()
    data = json.loads(raw)
    validate_backend(benchmark(data))
    output = args.output or EXPORTS / benchmark(data) / (data["model"].split("/")[-1] + ".json")
    protect_output(output)
    with lock_for(output, "run"):
        legacy.save(output, data)
        await run_job(data, digest(raw), "follow", output=output, source_path=source,
                      source_pid=args.pid, concurrency=1)


def retry_candidates(data, difficulty=None):
    candidates = []
    for task_id, task in data["tasks"].items():
        if difficulty and task.get("difficulty") != difficulty:
            continue
        for condition in CONDITIONS:
            solution = task[condition]
            status = solution.get("generation", {}).get("status")
            if status in ("api_error", "incomplete", "interrupted_legacy", "interrupted_storage") or (
                    not solution["code"] and status in (None, "pending")):
                candidates.append((task_id, condition))
    return candidates


def prepare_retry(data, output, difficulty=None):
    candidates = retry_candidates(data, difficulty)
    if not candidates:
        return data
    snapshot = CACHE / "retries" / digest(data) / output.name
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if snapshot.exists():
        if json.loads(snapshot.read_text()) != data:
            raise RuntimeError("retry snapshot differs; refusing to replace the original attempts")
    else:
        legacy.save(snapshot, data)
    updated = deepcopy(data)
    updated.setdefault("manual_retry_rounds", []).append({
        "started_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": str(snapshot.relative_to(ROOT)), "difficulty": difficulty,
        "outputs": [{"task_id": task_id, "condition": condition,
                     "previous_status": data["tasks"][task_id][condition].get("generation", {}).get("status")}
                    for task_id, condition in candidates],
        "note": "Explicitly requested completion round; no test/checker feedback supplied. Not first-attempt results."})
    for task_id, condition in candidates:
        updated["tasks"][task_id][condition] = {
            "code": "", "checker": legacy.not_run("awaiting requested completion round"),
            "official_tests": legacy.not_run("awaiting requested completion round")}
    print(f"Completion round: {len(candidates)} outputs; original attempts: {snapshot}", flush=True)
    return updated


async def generate(args, *, output_locked=False):
    global _API_KEY
    output = args.output or EXPORTS / args.benchmark / (args.model.split("/")[-1] + ".json")
    protect_output(output)
    with nullcontext() if output_locked else lock_for(output, "run"):
        data = legacy.prepare_results(output, args.model, args.benchmark)
        if any(t[c].get("generation", {}).get("status") == "in_progress" for t in data["tasks"].values() for c in CONDITIONS):
            raise RuntimeError("an existing request is unresolved; do not start overlapping generation into this file")
        if not args.generation_only:
            validate_backend(args.benchmark)
        api_url = (args.api_url or API_URLS[args.provider]).rstrip("/")
        settings = legacy.experiment_settings(data, args.provider, api_url, args.max_tokens)
        if data.get("experiment", settings) != settings:
            raise RuntimeError("generation settings differ; choose a new --output path")
        if args.provider != "openai":
            key_env = {"anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}[args.provider]
            _API_KEY = os.environ.get(key_env) or getpass.getpass(
                f"{args.provider} API key (hidden, not saved): ").strip()
            if args.provider == "anthropic":
                if api_url != API_URLS["anthropic"]:
                    raise RuntimeError("credentials are sent only to the official Anthropic HTTPS API")
                info = legacy.api_json(api_url + "/models/" + args.model, headers=legacy.anthropic_headers(_API_KEY))
                if info["id"] != args.model:
                    raise RuntimeError("requested Anthropic model ID did not match")
            else:
                if api_url != API_URLS["deepseek"]:
                    raise RuntimeError("credentials are sent only to the official DeepSeek HTTPS API")
                info = legacy.api_json(api_url + "/models", headers={"Authorization": "Bearer " + _API_KEY})
                if not any(m["id"] == args.model for m in info["data"]):
                    raise RuntimeError("requested DeepSeek model is unavailable")
        difficulty = getattr(args, "difficulty", None)
        if getattr(args, "retry_incomplete", False):
            data = prepare_retry(data, output, difficulty)
        data["experiment"] = settings
        legacy.save(output, data)
        try:
            await run_job(data, digest(data), "generate", output=output, provider=args.provider,
                          api_url=api_url, max_tokens=args.max_tokens, generation_only=args.generation_only,
                          concurrency=args.concurrency, difficulty=difficulty)
        finally:
            _API_KEY = None


def gpu(args):
    output = args.output or EXPORTS / args.benchmark / (args.model.split("/")[-1] + ".json")
    protect_output(output)
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("GPU inference must run in a Slurm allocation, never on a login node")
    with lock_for(output, "run"):
        data = legacy.prepare_results(output, args.model, args.benchmark)
        if any(t[c].get("generation", {}).get("status") == "in_progress" for t in data["tasks"].values() for c in CONDITIONS):
            raise RuntimeError("resolve the interrupted attempt before starting another GPU job")
        if all(t[c]["code"] or "generation" in t[c] for t in data["tasks"].values() for c in CONDITIONS):
            print("No unattempted outputs; vLLM was not started.")
            return

        def run_harbor(path, current, api_url, max_tokens):
            options = argparse.Namespace(output=path, benchmark=args.benchmark, model=args.model,
                provider="openai", api_url=api_url, max_tokens=max_tokens, generation_only=True, concurrency=1)
            asyncio.run(generate(options, output_locked=True))

        legacy.gpu_generate(output, data, args.model_path, args.model_revision, args.max_tokens,
                            32768 if args.benchmark == "livecodebench" else 16384,
                            generate_callback=run_harbor, server_python=args.inference_python)


def main():
    if version("harbor") != HARBOR_VERSION:
        raise RuntimeError(f"install the pinned harbor=={HARBOR_VERSION} environment")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    migration = sub.add_parser("migrate", help="import existing results with zero model calls")
    migration.add_argument("--file", action="append", type=Path)
    verification = migration.add_mutually_exclusive_group()
    verification.add_argument("--verify", dest="verify", action="store_true", default=True,
                              help="rerun the unchanged checker and official tests (default)")
    verification.add_argument("--recorded-only", dest="verify", action="store_false",
                              help="import historical verdicts without executing candidates")
    migration.add_argument("--limit", type=int, help="first N problems, both conditions; exports a separate parity file")
    migration.add_argument("--output", type=Path)
    migration.add_argument("--concurrency", type=int, default=1)
    generation = sub.add_parser("generate", help="one new model call per unattempted condition")
    generation.add_argument("--model", required=True)
    generation.add_argument("--benchmark", choices=["humaneval", "livecodebench"], required=True)
    generation.add_argument("--provider", choices=list(API_URLS), required=True)
    generation.add_argument("--api-url")
    generation.add_argument("--max-tokens", type=int, required=True)
    generation.add_argument("--output", type=Path)
    generation.add_argument("--generation-only", action="store_true", help="GPU/Linux: defer all code execution to the Mac verifier")
    generation.add_argument("--concurrency", type=int, default=1)
    generation.add_argument("--difficulty", choices=["medium", "hard"], help="generate only this LCB difficulty")
    generation.add_argument("--retry-incomplete", action="store_true",
                            help="explicit completion round: archive and retry incomplete/API-error outputs once")
    follower = sub.add_parser("follow", help="adopt a running legacy producer without issuing model requests")
    follower.add_argument("--file", required=True, type=Path)
    follower.add_argument("--pid", required=True, type=int, help="PID of the existing generator; stop waiting when it exits")
    follower.add_argument("--output", type=Path)
    gpu_parser = sub.add_parser("gpu", help="run one-shot Harbor generation inside a Slurm GPU allocation")
    gpu_parser.add_argument("--model", required=True)
    gpu_parser.add_argument("--benchmark", choices=["humaneval", "livecodebench"], required=True)
    gpu_parser.add_argument("--model-path", required=True, type=Path)
    gpu_parser.add_argument("--model-revision", required=True)
    gpu_parser.add_argument("--inference-python", required=True, type=Path,
                            help="existing vLLM interpreter; Harbor does not modify its packages")
    gpu_parser.add_argument("--max-tokens", type=int, required=True)
    gpu_parser.add_argument("--output", type=Path)
    export = sub.add_parser("export", help="recover the simple JSON from an existing Harbor job")
    export.add_argument("job", type=Path)
    export.add_argument("--output", type=Path)
    view = sub.add_parser("view", help="open the local Harbor results viewer")
    view.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if getattr(args, "limit", 1) is not None and getattr(args, "limit", 1) < 1:
        parser.error("--limit must be positive")
    if args.action == "migrate" and args.output and (not args.file or len(args.file) != 1):
        parser.error("--output requires exactly one --file")
    if args.action == "migrate":
        asyncio.run(migrate(args))
    elif args.action == "generate":
        if args.max_tokens < 1:
            parser.error("--max-tokens must be positive")
        if args.difficulty and args.benchmark != "livecodebench":
            parser.error("--difficulty requires --benchmark livecodebench")
        asyncio.run(generate(args))
    elif args.action == "follow":
        if args.pid <= 0:
            parser.error("--pid must be a positive generator PID")
        asyncio.run(follow(args))
    elif args.action == "gpu":
        if args.max_tokens < 1:
            parser.error("--max-tokens must be positive")
        gpu(args)
    elif args.action == "export":
        print(export_job(args.job, args.output))
    else:
        executable = Path(sys.executable).parent / "harbor"
        raise SystemExit(subprocess.call([str(executable), "view", str(JOBS), "--port", str(args.port)]))


if __name__ == "__main__":
    main()
