import contextlib
import json
import math
import os
from pathlib import Path
import resource
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback


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


def command(directory):
    python = str(Path(sys.executable).absolute())
    worker = str(Path(__file__).resolve())
    runtime = str(Path(sys.base_prefix).resolve())
    environment = str(Path(sys.prefix).resolve())
    if sys.platform == "darwin":
        profile = sandbox_profile(directory, [Path(worker)])
        profile += f"\n(allow file-read* (subpath {json.dumps(environment)}))\n"
        return ["/usr/bin/sandbox-exec", "-p", profile, python, "-I", worker]
    if sys.platform == "linux":
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise RuntimeError("Linux verification requires bubblewrap; install the bubblewrap package")
        args = [bwrap, "--unshare-all", "--die-with-parent", "--new-session"]
        paths = ["/usr", "/bin", "/lib", "/lib64"]
        for prefix in (runtime, environment):
            if not any(prefix == p or prefix.startswith(p + "/") for p in paths):
                paths.append(prefix)
        for path in paths:
            if Path(path).exists():
                args.extend(["--ro-bind", path, path])
        args.extend(["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                     "--bind", directory, directory, "--ro-bind", worker, "/worker.py",
                     "--chdir", directory, "--", python, "-I", "/worker.py"])
        return args
    raise RuntimeError("only macOS and Linux sandbox backends are supported")


def run(payload, timeout):
    with tempfile.TemporaryDirectory(prefix="purepy-evaluation-") as directory:
        payload = {**payload, "directory": directory, "timeout": timeout}
        if payload.get("benchmark") == "LiveCodeBench":
            (Path(directory) / "grader.py").write_text(payload.pop("grader_source"))
        try:
            process = subprocess.Popen(command(directory), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, cwd=directory, start_new_session=True,
                                       env={"PATH": "/usr/bin:/bin", "OPENBLAS_NUM_THREADS": "1",
                                            "OMP_NUM_THREADS": "1", "PYTHONHASHSEED": "0"})
        except (OSError, RuntimeError) as error:
            return {"passed": None, "error": str(error), "tooling_error": True}
        try:
            stdout, stderr = process.communicate(json.dumps(payload), timeout=timeout + 5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            return {"passed": False, "error": "candidate exceeded wall-clock limit", "tooling_error": False}
        if process.returncode != 0:
            return {"passed": None, "error": f"sandbox worker failed: {stderr[:2000] or process.returncode}",
                    "tooling_error": True}
        try:
            verdict = json.loads(stdout)
            if not isinstance(verdict.get("passed"), bool) and verdict.get("passed") is not None:
                raise ValueError("invalid verdict")
            if "passed" not in verdict or "tooling_error" not in verdict:
                raise ValueError("missing verdict fields")
            return verdict
        except (ValueError, TypeError):
            return {"passed": None, "error": "sandbox did not return a valid verdict", "tooling_error": True}


def worker():
    payload = json.load(sys.stdin)
    limit = float(payload["timeout"])
    resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(limit), math.ceil(limit) + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))

    def expired(signum, frame):
        raise TimeoutError("candidate exceeded test time limit")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, limit)
    grader = None
    if payload["benchmark"] == "LiveCodeBench":
        try:
            import numpy as np
            grader = runpy.run_path(str(Path(payload["directory"]) / "grader.py"))["run_test"]
        except BaseException:
            print(json.dumps({"passed": None, "error": "official grader could not load",
                              "tooling_error": True}))
            return
    try:
        if payload["benchmark"] == "LiveCodeBench":
            with tempfile.TemporaryFile(mode="w+", dir=payload["directory"]) as capture:
                with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                    outcomes, metadata = grader(payload["sample"], test=payload["code"], timeout=6)
            outcomes = [r.item(0) if isinstance(r, np.ndarray) else r for r in outcomes]
            result = {"passed": len(outcomes) == payload["test_count"] and all(r > 0 for r in outcomes),
                      "error": None if all(r > 0 for r in outcomes) else json.dumps(metadata, default=str),
                      "tests_passed": int(sum(r > 0 for r in outcomes)), "tests_total": payload["test_count"],
                      "tooling_error": False}
        else:
            with tempfile.TemporaryFile(mode="w+", dir=payload["directory"]) as capture:
                with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                    exec(compile(payload["program"], "solution_and_official_tests.py", "exec"), {})
            result = {"passed": True, "error": None, "tooling_error": False}
    except BaseException:
        tooling = payload["benchmark"] == "LiveCodeBench"
        result = {"passed": None if tooling else False, "error": traceback.format_exc().strip(),
                  "tooling_error": tooling}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    print(json.dumps(result))


if __name__ == "__main__":
    worker()
