#!/usr/bin/env python3
"""PurePy test runner.

Discovers tests by directory, runs them with parallelism, reports results.
Replaces the older Bash version. Written in a PurePy-leaning style: small
functions, return-values-not-side-effects, list/dict over mutable accumulators.
"""

import pathlib
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple


ROOT = pathlib.Path(__file__).resolve().parent.parent
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


# ---- Per-rule expectations ---------------------------------------------------
# Ill-formed/semantic tests for which `purepy_check.py` currently catches the
# error. Expand as we implement more rules.

SEMANTIC_CAUGHT = {
    "duplicate_def_in_region",
    "unreachable",
    "self_capture",
    "self_capture_lambda",
}


# ---- Result type -------------------------------------------------------------


@dataclass
class Result:
    label: str
    passed: bool
    message: Optional[str] = None


def format_result(r: Result) -> str:
    mark = f"{GREEN}✓{RESET}" if r.passed else f"{RED}✗{RESET}"
    suffix = "" if r.passed else f" ({r.message})"
    return f"  {mark} {r.label}{suffix}"


# ---- Steps -------------------------------------------------------------------


def run_proc(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True)


def step_exit_0(label: str, cmd: List[str]) -> Result:
    proc = run_proc(cmd)
    if proc.returncode == 0:
        return Result(label, True)
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    return Result(label, False, f"exit {proc.returncode}: {stderr}")


def step_expect_exit(label: str, cmd: List[str], expected: int) -> Result:
    proc = run_proc(cmd)
    if proc.returncode == expected:
        return Result(label, True)
    return Result(label, False, f"expected exit {expected}, got {proc.returncode}")


# ---- Commands ----------------------------------------------------------------


def parse_cmd(path: pathlib.Path) -> List[str]:
    return ["python3", str(ROOT / "src" / "purepy_parse.py"), str(path)]


def check_cmd(path: pathlib.Path) -> List[str]:
    return ["python3", str(ROOT / "src" / "purepy_check.py"), str(path)]


def step_run(label: str, interpreter: str, path: pathlib.Path) -> Result:
    """Run the script under the given Python interpreter, compare output to .expected
    (or check for expected exception class in stderr if .exception.expected exists)."""
    expected_path = path.with_suffix(".expected")
    exception_path = path.with_suffix(".exception.expected")

    if exception_path.exists():
        expected_type = exception_path.read_text().strip()
        proc = subprocess.run([interpreter, str(path)], capture_output=True)
        if proc.returncode == 0:
            return Result(label, False, f"expected {expected_type} but script succeeded")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        if expected_type not in stderr:
            return Result(label, False, f"expected {expected_type}, got: {stderr.strip()[:200]}")
        return Result(label, True)

    if not expected_path.exists():
        return Result(label, False, "no .expected file")

    expected = expected_path.read_text()
    proc = subprocess.run([interpreter, str(path)], capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()[:200]
        return Result(label, False, f"exit {proc.returncode}: {stderr}")
    actual = proc.stdout.decode("utf-8", errors="replace")
    if actual != expected:
        return Result(label, False, f"output mismatch (expected {expected!r}, got {actual!r})")
    return Result(label, True)


# ---- Per-category step builders ----------------------------------------------
# Each returns a list of thunks (no-arg callables returning a Result).


Thunk = Callable[[], Result]


def steps_well_formed(path: pathlib.Path, interpreter: str) -> List[Thunk]:
    p = str(path.relative_to(ROOT))
    return [
        lambda: step_exit_0(f"{p} (parse)", parse_cmd(path)),
        lambda: step_exit_0(f"{p} (check)", check_cmd(path)),
        lambda: step_run(f"{p} (run)", interpreter, path),
    ]


def steps_well_formed_pending(path: pathlib.Path) -> List[Thunk]:
    p = str(path.relative_to(ROOT))
    return [lambda: step_expect_exit(p, parse_cmd(path), 2)]


def steps_ill_formed_semantic(path: pathlib.Path, interpreter: str) -> List[Thunk]:
    p = str(path.relative_to(ROOT))
    thunks: List[Thunk] = [lambda: step_exit_0(f"{p} (parse)", parse_cmd(path))]
    if path.stem in SEMANTIC_CAUGHT:
        thunks.append(lambda: step_expect_exit(f"{p} (check)", check_cmd(path), 3))
    thunks.append(lambda: step_run(f"{p} (run)", interpreter, path))
    return thunks


def steps_ill_formed_unsupported(path: pathlib.Path) -> List[Thunk]:
    p = str(path.relative_to(ROOT))
    return [lambda: step_expect_exit(p, parse_cmd(path), 1)]


# ---- Discovery ---------------------------------------------------------------


def discover() -> List[Tuple[str, List[pathlib.Path], Callable[[pathlib.Path, str], List[Thunk]]]]:
    base = ROOT / "test"
    wf = base / "well-formed"

    wf_files = (
        sorted(wf.glob("*.py"))
        + sorted((wf / "conditionals").glob("*.py"))
        + sorted((wf / "functions").glob("*.py"))
        + sorted((wf / "scopes").glob("*.py"))
    )
    pending_files = sorted((wf / "pending").glob("*.py"))
    semantic_files = sorted((base / "ill-formed" / "semantic").glob("*.py"))
    unsupported_files = sorted((base / "ill-formed" / "unsupported").glob("*.py"))

    return [
        ("well-formed", wf_files, steps_well_formed),
        ("well-formed/pending", pending_files, lambda p, _: steps_well_formed_pending(p)),
        ("ill-formed/semantic", semantic_files, steps_ill_formed_semantic),
        ("ill-formed/unsupported", unsupported_files, lambda p, _: steps_ill_formed_unsupported(p)),
    ]


# ---- Execution ---------------------------------------------------------------


def run_test_steps(thunks: List[Thunk]) -> List[Result]:
    """Steps for one test run sequentially (one depends on previous in spirit)."""
    return [t() for t in thunks]


def run_section(name: str, files: List[pathlib.Path], steps_fn, interpreter: str) -> List[Result]:
    print(name)
    results: List[Result] = []
    for path in files:
        for r in run_test_steps(steps_fn(path, interpreter)):
            print(format_result(r))
            results.append(r)
    return results


def main() -> None:
    interpreter = sys.argv[1] if len(sys.argv) > 1 else "python3"

    all_results: List[Result] = []
    for name, files, steps_fn in discover():
        all_results.extend(run_section(name, files, steps_fn, interpreter))

    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    failed = total - passed

    print()
    if failed:
        print(f"{RED}✗ {passed}/{total} passed, {failed} failed{RESET}")
        sys.exit(1)
    print(f"{GREEN}✓ {total}/{total} passed{RESET}")


if __name__ == "__main__":
    main()
