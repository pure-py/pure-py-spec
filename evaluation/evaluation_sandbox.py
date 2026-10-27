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
    (allow process-fork)
    (allow ipc-posix-sem)
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


def run(payload, timeout, files=None):
    from evaluation_benchmarks import Verdict
    with tempfile.TemporaryDirectory(prefix="purepy-evaluation-") as directory:
        payload = {**payload, "directory": directory, "timeout": timeout}
        module = Path(__file__).with_name("evaluation_benchmarks.py")
        (Path(directory) / module.name).write_text(module.read_text())
        for name, source in (files or {}).items():
            (Path(directory) / name).write_text(source)
        try:
            process = subprocess.Popen(command(directory), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, cwd=directory, start_new_session=True,
                                       env={"PATH": "/usr/bin:/bin", "OPENBLAS_NUM_THREADS": "1",
                                            "OMP_NUM_THREADS": "1", "PYTHONHASHSEED": "0"})
        except (OSError, RuntimeError) as error:
            return Verdict(None, str(error), True)
        try:
            stdout, stderr = process.communicate(json.dumps(payload), timeout=timeout + 5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            return Verdict(False, "candidate exceeded wall-clock limit", False)
        if process.returncode != 0:
            return Verdict(None, f"sandbox worker failed: {stderr[:2000] or process.returncode}", True)
        try:
            verdict = json.loads(stdout)
            if not isinstance(verdict.get("passed"), bool) and verdict.get("passed") is not None:
                raise ValueError("invalid verdict")
            if "passed" not in verdict or "tooling_error" not in verdict:
                raise ValueError("missing verdict fields")
            return Verdict(**verdict)
        except (ValueError, TypeError):
            return Verdict(None, "sandbox did not return a valid verdict", True)


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
    module = runpy.run_path(str(Path(payload["directory"]) / "evaluation_benchmarks.py"))
    benchmark = None if "probe" in payload else module["BENCHMARKS"][payload["benchmark"]]()
    Verdict = module["Verdict"]
    encode_verdict = module["encode_verdict"]
    try:
        grader = benchmark.prepare_worker(payload) if benchmark is not None else None
    except BaseException:
        print(json.dumps(Verdict(None, "official grader could not load", True), default=encode_verdict))
        return
    try:
        with tempfile.TemporaryFile(mode="w+", dir=payload["directory"]) as capture:
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                if benchmark is None:
                    exec(compile(payload["probe"], "sandbox_probe.py", "exec"), {})
                    result = Verdict(True, None, False)
                else:
                    result = benchmark.execute(payload, grader)
    except BaseException:
        tooling = benchmark is None or benchmark.worker_tooling_errors
        result = Verdict(None if tooling else False, traceback.format_exc().strip(), tooling)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    print(json.dumps(result, default=encode_verdict))


if __name__ == "__main__":
    worker()
