"""Harbor trials for runs of the evaluation pipeline: one trial per problem and condition."""

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
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

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.environments.capabilities import EnvironmentCapabilities
from harbor.job import Job
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import AgentConfig, EnvironmentConfig, TaskConfig, VerifierConfig
from harbor.models.verifier.result import VerifierResult
from harbor.verifier.base import BaseVerifier

from evaluation import CONDITIONS, save


ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache/harbor"
JOBS = CACHE / "jobs"
HARBOR_VERSION = "0.24.0"


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def benchmark(data):
    return data["benchmark"].lower().replace("+", "-plus")


class EvaluationFiles(BaseEnvironment):
    """File-only environment: no shell, no network, nothing executes here."""

    @staticmethod
    def type():
        return "purepy-files"

    @property
    def capabilities(self):
        return EnvironmentCapabilities()

    def _validate_definition(self):
        marker = json.loads((self.environment_dir / "adapter.json").read_text())
        if marker != {"adapter": "purepy-files", "version": 2}:
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
        raise RuntimeError("shell execution is disabled in the evaluation environment")

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


class RecordedAgent(BaseAgent):
    """Replays the answer recorded by the evaluation pipeline; makes no model calls."""

    @staticmethod
    def name():
        return "purepy-recorded"

    def version(self):
        return "2"

    async def setup(self, environment):
        if not isinstance(environment, EvaluationFiles):
            raise TypeError("this agent requires EvaluationFiles")

    async def run(self, instruction, environment, context):
        record = json.loads((environment.environment_dir.parent / "record.json").read_text())
        if digest(instruction.encode()) != record["prompt_sha256"]:
            raise RuntimeError("the trial instruction differs from the recorded prompt")
        solution = deepcopy(record["solution"])
        usage = solution.get("generation", {}).get("usage") or {}
        context.n_input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        context.n_output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
        context.cost_usd = 0
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        save(self.logs_dir / "answer.json", solution)
        (self.logs_dir / "solution.py").write_text(solution["code"] + "\n")
        for attempt in solution.get("attempts", []):
            (self.logs_dir / f"round-{attempt['round']}.py").write_text(attempt["code"] + "\n")
        environment.answer = solution
        context.metadata = {"task_id": record["task_id"], "condition": record["condition"],
                            "generation": solution.get("generation"), "output_format": solution.get("output_format")}


def rewards_for(solution):
    checker = solution["checker"]["passed"]
    tests = solution["official_tests"]["passed"]
    rewards = {"code_present": int(bool(solution["code"])),
               "checker_evaluated": int(isinstance(checker, bool)),
               "tests_evaluated": int(isinstance(tests, bool)),
               "rejections": solution.get("rejections", 0),
               "attempts": len(solution.get("attempts", []))}
    if isinstance(checker, bool):
        rewards["checker_passed"] = int(checker)
    if isinstance(tests, bool):
        rewards["official_tests_passed"] = int(tests)
    if isinstance(checker, bool) and isinstance(tests, bool):
        rewards["joint_passed"] = int(checker and tests)
    if solution.get("rounds_to_acceptance") is not None:
        rewards["rounds_to_acceptance"] = solution["rounds_to_acceptance"]
    return rewards


class RecordedVerifier(BaseVerifier):
    """Rewards come from the verdicts the pipeline recorded; nothing is re-run."""

    async def verify(self):
        solution = deepcopy(self.environment.answer)
        folder = self.trial_paths.verifier_dir
        folder.mkdir(parents=True, exist_ok=True)
        save(folder / "verdict.json", solution)
        rewards = rewards_for(solution)
        save(folder / "reward.json", rewards)
        return VerifierResult(rewards=rewards)


def task_name(task_id, condition):
    return task_id.lower().replace("/", "-") + "-" + condition


def materialize(data, source_sha):
    identity = digest({"adapter": "2.0", "source": source_sha})[:16]
    bundle = CACHE / "tasks" / identity
    records = []
    for task_id, task in data["tasks"].items():
        for condition in CONDITIONS:
            if condition not in task:
                continue
            solution = task[condition]
            folder = bundle / task_name(task_id, condition)
            cached = folder / "record.json"
            if cached.exists():
                old = json.loads(cached.read_text())
                if old.get("solution") != solution or old.get("model") != data["model"]:
                    raise RuntimeError("cached Harbor task inputs changed; refusing to rewrite a frozen bundle")
                records.append({"task_id": task_id, "condition": condition, "path": str(folder)})
                continue
            (folder / "environment").mkdir(parents=True, exist_ok=True)
            (folder / "tests").mkdir(exist_ok=True)
            prompt = solution["prompt"]
            record = {"task_id": task_id, "condition": condition, "benchmark": benchmark(data),
                      "model": data["model"], "task": {k: v for k, v in task.items() if k not in CONDITIONS},
                      "solution": solution, "prompt_sha256": digest(prompt.encode())}
            save(folder / "record.json", record)
            save(folder / "environment/adapter.json", {"adapter": "purepy-files", "version": 2})
            (folder / "instruction.md").write_text(prompt)
            (folder / "task.toml").write_text(
                'version = "1.0"\n\n[metadata]\n' + f'task_id = {json.dumps(task_id)}\ncondition = {json.dumps(condition)}\n'
                + f'difficulty = {json.dumps(task.get("difficulty", "unspecified"))}\n'
                + '\n[verifier]\ntimeout_sec = 60\n\n[environment]\nbuild_timeout_sec = 30\n')
            (folder / "tests/test.sh").write_text('#!/bin/sh\nexit 1\n')
            records.append({"task_id": task_id, "condition": condition, "path": str(folder)})
    return identity, records


async def import_run(source, output, concurrency):
    raw = source.read_bytes()
    data = json.loads(raw)
    source_sha = digest(raw)
    output = output or source.parent / "harbor" / source.name
    if output.resolve() == source.resolve():
        raise RuntimeError("the Harbor export must not overwrite the pipeline's result file")
    identity, records = materialize(data, source_sha)
    if not records:
        raise RuntimeError("the result file contains no answers to import")
    label = data["model"].split("/")[-1].lower()
    config = JobConfig(
        job_name=f"{benchmark(data)}-{label}-{identity}", jobs_dir=JOBS, n_attempts=1,
        n_concurrent_trials=concurrency, quiet=True, retry={"max_retries": 0},
        environment=EnvironmentConfig(import_path="harbor_runner:EvaluationFiles"),
        verifier=VerifierConfig(import_path="harbor_runner:RecordedVerifier"),
        agents=[AgentConfig(import_path="harbor_runner:RecordedAgent", model_name=data["model"])],
        tasks=[TaskConfig(path=Path(r["path"]),
                          source=f"{benchmark(data)}-{data['tasks'][r['task_id']].get('difficulty', 'all')}-{r['condition']}")
               for r in records])
    job = await Job.create(config)
    save(job.job_dir / "purepy.json", {"source": str(source), "source_sha256": source_sha,
                                       "records": records, "data": data})
    print(f"Harbor job: {job.job_dir} ({len(records)} trials)", flush=True)
    await job.run()
    destination = export_job(job.job_dir, output)
    print(f"Exported: {destination}", flush=True)
    stats = json.loads((job.job_dir / "result.json").read_text())["stats"]
    if stats["n_errored_trials"]:
        raise RuntimeError(f"{stats['n_errored_trials']} Harbor trials errored; see {job.job_dir}")


def export_job(job_dir, output=None):
    job_dir = Path(job_dir).resolve()
    manifest = json.loads((job_dir / "purepy.json").read_text())
    data = deepcopy(manifest["data"])
    index = {r["path"]: r for r in manifest["records"]}
    found = 0
    for config_file in job_dir.glob("*/config.json"):
        config = json.loads(config_file.read_text())
        record = index.get(str(Path(config["task"]["path"]).resolve()))
        if record is None:
            continue
        verdict = config_file.parent / "verifier/verdict.json"
        if not verdict.exists():
            continue
        solution = json.loads(verdict.read_text())
        original = data["tasks"][record["task_id"]][record["condition"]]
        if solution["code"] != original["code"]:
            raise RuntimeError("the Harbor trial changed the recorded code")
        found += 1
    destination = output or Path(manifest["source"]).parent / "harbor" / Path(manifest["source"]).name
    reference = str(job_dir.relative_to(ROOT.resolve())) if job_dir.is_relative_to(ROOT.resolve()) else str(job_dir)
    data["harbor"] = {"version": HARBOR_VERSION, "job": reference, "source": manifest["source"],
                      "source_sha256": manifest["source_sha256"],
                      "trials_exported": found, "trials_expected": len(index),
                      "exported_at": datetime.now(timezone.utc).isoformat()}
    save(destination, data)
    if found != len(index):
        print(f"WARNING: {found}/{len(index)} trials exported; inspect {job_dir}", flush=True)
    return destination


def main():
    if version("harbor") != HARBOR_VERSION:
        raise RuntimeError(f"install the pinned harbor=={HARBOR_VERSION} environment")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    importer = sub.add_parser("import", help="record a pipeline run as Harbor trials, without model calls")
    importer.add_argument("--file", required=True, type=Path)
    importer.add_argument("--output", type=Path, help="export path; default results/RUN/harbor/MODEL.json")
    importer.add_argument("--concurrency", type=int, default=1)
    export = sub.add_parser("export", help="write the simple JSON export of an existing Harbor job")
    export.add_argument("job", type=Path)
    export.add_argument("--output", type=Path)
    view = sub.add_parser("view", help="open the local Harbor results viewer")
    view.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.action == "import":
        if args.concurrency < 1:
            parser.error("--concurrency must be positive")
        asyncio.run(import_run(args.file, args.output, args.concurrency))
    elif args.action == "export":
        print(export_job(args.job, args.output))
    else:
        executable = Path(sys.executable).parent / "harbor"
        raise SystemExit(subprocess.call([str(executable), "view", str(JOBS), "--port", str(args.port)]))


if __name__ == "__main__":
    main()
