from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import importlib.resources
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum

SUITE = "conformance-suite"
GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

EXPECTED = ".expected"
EXCEPTION_EXPECTED = f".exception{EXPECTED}"
ERROR_EXPECTED = f".error{EXPECTED}"
STATUS_EXPECTED = f".status{EXPECTED}"
OUTPUT_EXPECTED = f".output{EXPECTED}"
ARGS = ".args"  # command-line arguments, one per line

HELPERS = "helpers"
MAIN = "main.py"
BUG = "-bug"  # suffix of a directory of tests failing under a reported bug of the tool named
MYPY = "mypy"


class PythonOutcome(StrEnum):
    REJECTS = "python-rejects"
    RAISES = "python-raises"
    SUCCEEDS = "python-succeeds"


class PurePyOutcome(StrEnum):
    PARSER_REJECTS = "parser-rejects"
    TYPING_REJECTS = "typing-rejects"
    EXCLUDED_FOR_NOW = "excluded-for-now"
    UNDEFINED = "undefined"
    AGREES = "agrees"


SYNTAX_ERROR = "SyntaxError"


class Classification(StrEnum):
    """Wording of the classification in a diagnostic for an excluded Python feature."""

    BY_DESIGN = "not allowed in PurePy (excluded by design)"
    FOR_NOW = "not allowed in PurePy (excluded from this version)"


def excluded(feature: str, classification: Classification) -> str:
    """Diagnostic for a rejection of feature, with its classification."""
    return f"{feature} {classification}"


# Placeholder for classification at end of expected error for excluded feature
CLASSIFICATION = "{classification}"

CLASSIFICATION_OF: dict[PurePyOutcome, Classification] = {
    PurePyOutcome.PARSER_REJECTS: Classification.BY_DESIGN,
    PurePyOutcome.TYPING_REJECTS: Classification.BY_DESIGN,
    PurePyOutcome.EXCLUDED_FOR_NOW: Classification.FOR_NOW,
}


def expected_error(text: str, purepy: PurePyOutcome) -> str:
    """Expected error, with a trailing classification placeholder replaced by the full diagnostic."""
    if text.endswith(f" {CLASSIFICATION}"):
        return excluded(text.removesuffix(f" {CLASSIFICATION}"), CLASSIFICATION_OF[purepy])
    return text


class Exit(IntEnum):
    OK = 0
    NOT_ALLOWED = 1
    ILL_FORMED = 3
    UNDEFINED = 4  # Interpreter: run aborted with undefined behaviour
    EXCLUDED_FOR_NOW = 5  # Feature excluded from this version, found by parser or type checker


# Type checker exit status for each PurePy outcome, and whether its output contains .error.expected
TYPE_CHECKER_VERDICT: dict[PurePyOutcome, tuple[Exit, bool]] = {
    PurePyOutcome.PARSER_REJECTS: (Exit.NOT_ALLOWED, True),
    PurePyOutcome.TYPING_REJECTS: (Exit.ILL_FORMED, True),
    PurePyOutcome.EXCLUDED_FOR_NOW: (Exit.EXCLUDED_FOR_NOW, True),
    PurePyOutcome.UNDEFINED: (Exit.OK, False),
    PurePyOutcome.AGREES: (Exit.OK, False),
}


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


class Runtime(StrEnum):
    CPYTHON = "cpython"
    GRAALPY = "graalpy"
    PYODIDE = "pyodide"


RUNTIME_QUERY = "import platform, sys; print(platform.python_implementation(), sys.platform)"


def runtime(interpreter: list[str]) -> Runtime:
    implementation, system = run([*interpreter, "-c", RUNTIME_QUERY]).stdout.split()
    if system == "emscripten":
        return Runtime.PYODIDE
    return {"CPython": Runtime.CPYTHON, "GraalVM": Runtime.GRAALPY}[implementation]


def main_module(test: pathlib.Path) -> pathlib.Path:
    return test / MAIN if test.is_dir() else test


def filing_errors(path: pathlib.Path, outcome: PythonOutcome, undefined: bool) -> list[str]:
    """Expectation files of the test at path which do not match its directory"""
    expected = path.with_suffix(EXPECTED)
    exception = path.with_suffix(EXCEPTION_EXPECTED)
    both = expected.exists() and exception.exists()
    if both and not undefined or not (expected.exists() or exception.exists()):
        return [f"run: needs exactly one of {expected.name} and {exception.name}"]
    if not both and (outcome == PythonOutcome.SUCCEEDS) != expected.exists():
        return [f"run: misfiled, has {expected.name if expected.exists() else exception.name}"]
    name = exception.read_text().strip() if exception.exists() else None
    if name is not None and (outcome == PythonOutcome.REJECTS) != name.startswith(SYNTAX_ERROR):
        return [f"run: misfiled, expects {name}"]
    return []


def under_bug(stage: str, failures: list[str], test: pathlib.Path, tool: str) -> list[str]:
    """Failures of a stage of a test, inverted if the test is filed under a reported bug of tool"""
    if f"{tool}{BUG}" not in test.parts:
        return failures
    return [] if len(failures) > 0 else [f"{stage}: passes, but filed as a reported {tool} bug"]


def output_mismatch(path: pathlib.Path, proc: subprocess.CompletedProcess[str]) -> list[str]:
    """Check that running test at path gave expected exit status and output"""
    status_path = path.with_suffix(STATUS_EXPECTED)
    status = int(status_path.read_text()) if status_path.exists() else 0
    if proc.returncode != status:
        return [f"run: exit {proc.returncode}, expected {status}: {proc.stderr.strip()}"]
    if proc.stdout != path.with_suffix(EXPECTED).read_text():
        return ["run: output mismatch"]
    return []


def exception_mismatch(path: pathlib.Path, proc: subprocess.CompletedProcess[str]) -> list[str]:
    """Check that running test at path printed expected output, then raised expected exception"""
    name = path.with_suffix(EXCEPTION_EXPECTED).read_text().strip()
    if proc.returncode == 0:
        return [f"run: expected {name} but script succeeded"]
    if name not in proc.stderr:
        return [f"run: expected {name}, got: {proc.stderr.strip()}"]
    output = path.with_suffix(OUTPUT_EXPECTED)
    if proc.stdout != (output.read_text() if output.exists() else ""):
        return ["run: output before the exception mismatch"]
    return []


class Results:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[str] = []
        self.failures: list[str] = []

    @contextlib.contextmanager
    def test(self, label: object) -> Iterator[None]:
        self.failures = []
        yield
        self.record(label, self.failures)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def record(self, label: object, failures: list[str]) -> None:
        if len(failures) > 0:
            self.failed.append(str(label))
            print(f"  {RED}✗{RESET} {label} ({'; '.join(failures)})")
        else:
            self.passed += 1
            print(f"  {GREEN}✓{RESET} {label}")
        if os.environ.get("REPORT"):
            print(f"report: {label}\t{'failed' if len(failures) > 0 else 'passed'}")

    def summary(self) -> None:
        total = self.passed + len(self.failed)
        print()
        if len(self.failed) > 0:
            print(f"{RED}✗ {self.passed}/{total} passed, {len(self.failed)} failed{RESET}")
        else:
            print(f"{GREEN}✓ {total}/{total} passed{RESET}")


@dataclass
class Runner(Results):
    type_checker: list[str]
    interpreter: list[str] | None  # None: tests not run
    python_mode: bool  # Suite checked against Python and mypy
    check_messages: bool  # Diagnostics checked against reference type checker
    runtime: Runtime | None = field(init=False)

    def __post_init__(self) -> None:
        super().__init__()
        self.runtime = None if self.interpreter is None else runtime(self.interpreter)

    def run_type_checker(self, test: pathlib.Path) -> subprocess.CompletedProcess[str]:
        """Type-check a copy of test in a temporary directory, so that tests cannot interfere and the type
        checker writes nothing into the suite"""
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / test.name
            if test.is_dir():
                shutil.copytree(test, copy)
                return run([*self.type_checker, MAIN], cwd=copy)
            shutil.copy(test, copy)
            return run([*self.type_checker, test.name], cwd=copy.parent)

    def check_verdict(
        self, test: pathlib.Path, exit: Exit, error_expected: bool, purepy: PurePyOutcome
    ) -> list[str]:
        proc = self.run_type_checker(test)
        output = (proc.stdout + proc.stderr).strip()
        if proc.returncode != exit:
            return [
                f"check: exit {proc.returncode}, expected {int(exit)}: {output.split(chr(10), 1)[0]}"
            ]
        if not error_expected:
            return []
        error = main_module(test).with_suffix(ERROR_EXPECTED)
        if not error.exists():
            return [f"check: missing {error.name}"]
        expected = expected_error(error.read_text().strip(), purepy)
        if expected not in output:
            return [f"check: expected {expected!r}, got: {output}"]
        return []

    def check_mypy_accepts(self, test: pathlib.Path) -> list[str]:
        proc = self.run_type_checker(test)
        output = (proc.stdout + proc.stderr).strip()
        failures = (
            [] if proc.returncode == 0 else [f"check: rejected: {output.split(chr(10), 1)[0]}"]
        )
        return under_bug("check", failures, test, MYPY)

    def interpret(self, path: pathlib.Path, outcome: PythonOutcome, undefined: bool) -> list[str]:
        if self.interpreter is None:
            return []
        misfiled = filing_errors(path, outcome, undefined)
        if len(misfiled) > 0:
            return misfiled
        args_path = path.with_suffix(ARGS)
        args = args_path.read_text().splitlines() if args_path.exists() else []
        proc = run([*self.interpreter, path.name, *args], cwd=path.parent)
        both = path.with_suffix(EXPECTED).exists() and path.with_suffix(EXCEPTION_EXPECTED).exists()
        succeeds = proc.returncode == 0 if both else outcome == PythonOutcome.SUCCEEDS
        failures = (
            []
            if undefined and proc.returncode == Exit.UNDEFINED
            else output_mismatch(path, proc)
            if succeeds
            else exception_mismatch(path, proc)
        )
        return failures if self.runtime is None else under_bug("run", failures, path, self.runtime)

    def run_test(self, suite: pathlib.Path, test: pathlib.Path) -> list[str]:
        """Run test, taking Python and PurePy outcomes from first two directories of path within suite"""
        dirs = test.relative_to(suite).parts[:-1]
        python_outcome, purepy = PythonOutcome(dirs[0]), PurePyOutcome(dirs[1])
        exit, error_expected = TYPE_CHECKER_VERDICT[purepy]
        path = main_module(test)
        well_formed = exit == Exit.OK
        undefined = purepy == PurePyOutcome.UNDEFINED
        if self.python_mode:
            return [
                *(self.check_mypy_accepts(test) if well_formed else []),
                *self.interpret(path, python_outcome, undefined),
            ]
        return [
            *self.check_verdict(test, exit, error_expected and self.check_messages, purepy),
            *(self.interpret(path, python_outcome, undefined) if well_formed else []),
        ]

    def run_suite(self, suite: pathlib.Path, jobs: int | None) -> None:
        """Run tests in parallel on jobs threads, one per core by default, and report results in order"""
        found = list(tests(suite))
        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            results = pool.map(lambda test: self.run_test(suite, test), found)
            last = None
            for test, failures in zip(found, results):
                header = test.parent.relative_to(suite)
                if header != last:
                    print(header)
                    last = header
                self.record(test.relative_to(suite), failures)


def is_well_formed(suite: pathlib.Path, test: pathlib.Path) -> bool:
    return TYPE_CHECKER_VERDICT[PurePyOutcome(test.relative_to(suite).parts[1])][0] == Exit.OK


def tests(suite: pathlib.Path) -> Iterator[pathlib.Path]:
    """Tests sorted by path: a module as a .py file, or a program as the directory holding its main
    module."""
    found = [
        path
        for path in suite.rglob("*.py")
        if HELPERS not in path.parts and "__pycache__" not in path.parts
    ]
    programs = {path.parent for path in found if path.name == MAIN}
    modules = [path for path in found if not any(d in programs for d in path.parents)]
    yield from sorted([*programs, *modules], key=lambda test: (test.parent.as_posix(), test.name))


@contextlib.contextmanager
def suite() -> Iterator[pathlib.Path]:
    with importlib.resources.as_file(importlib.resources.files(__package__) / SUITE) as path:
        yield path


def check_conformance(argv: Sequence[str] | None = None) -> Runner:
    parser = argparse.ArgumentParser(prog="purepy-conformance")
    parser.add_argument("interpreter", nargs="?", default="python3")
    parser.add_argument(
        "--type-checker",
        default="purepy --check",
        help="command which type-checks the module at the path appended to it (default: purepy --check)",
    )
    parser.add_argument(
        "--no-run", action="store_true", help="check the tests without running them"
    )
    parser.add_argument(
        "--python-mode",
        action="store_true",
        help="check the suite against Python and mypy. Every test must have its recorded Python outcome, and "
        "mypy must accept every test which is well-formed in PurePy",
    )
    parser.add_argument(
        "--check-messages",
        action="store_true",
        help="check diagnostics against those of the reference type checker",
    )
    parser.add_argument(
        "--jobs", type=int, help="number of tests run in parallel (default: number of cores)"
    )
    args = parser.parse_args(argv)
    runner = Runner(
        shlex.split(args.type_checker),
        None if args.no_run else shlex.split(args.interpreter),
        args.python_mode,
        args.check_messages,
    )
    with suite() as path:
        runner.run_suite(path, args.jobs)
        found = list(tests(path))
        checked = sum(1 for test in found if is_well_formed(path, test))
    runner.summary()
    if args.python_mode:
        print(f"Python mode: {checked} tests type-checked and run, {len(found) - checked} run only")
    return runner


def main(argv: Sequence[str] | None = None) -> None:
    sys.exit(1 if len(check_conformance(argv).failed) > 0 else 0)


if __name__ == "__main__":
    main()
