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
from enum import IntEnum, StrEnum
from typing import NamedTuple

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
MYPY_BUG = "mypy-bug"


class PythonOutcome(StrEnum):
    REJECTS = "python-rejects"
    RAISES = "python-raises"
    SUCCEEDS = "python-succeeds"


class PurePyOutcome(StrEnum):
    PARSER_REJECTS = "parser-rejects"
    TYPING_REJECTS = "typing-rejects"
    NOT_YET_SPECIFIED = "not-yet-specified"
    UNDEFINED = "undefined"
    AGREES = "agrees"


SYNTAX_ERROR = "SyntaxError"


class Exit(IntEnum):
    OK = 0
    NOT_ALLOWED = 1
    ILL_FORMED = 3
    UNDEFINED = 4  # Interpreter: run aborted with undefined behaviour
    NOT_YET_SPECIFIED = 5  # Type checker: program uses feature not yet specified


class Expectation(NamedTuple):
    exit: Exit
    error_expected: bool  # type checker output contains .error.expected
    python: PythonOutcome


# Type checker verdict for each PurePy outcome
TYPE_CHECKER_VERDICT: dict[PurePyOutcome, tuple[Exit, bool]] = {
    PurePyOutcome.PARSER_REJECTS: (Exit.NOT_ALLOWED, True),
    PurePyOutcome.TYPING_REJECTS: (Exit.ILL_FORMED, True),
    PurePyOutcome.NOT_YET_SPECIFIED: (Exit.NOT_YET_SPECIFIED, True),
    PurePyOutcome.UNDEFINED: (Exit.OK, False),
    PurePyOutcome.AGREES: (Exit.OK, False),
}


def expectation(python: PythonOutcome, purepy: PurePyOutcome) -> Expectation:
    exit, error_expected = TYPE_CHECKER_VERDICT[purepy]
    return Expectation(exit, error_expected, python)


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


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
        if failures:
            self.failed.append(f"{label} ({'; '.join(failures)})")
            print(f"  {RED}✗{RESET} {self.failed[-1]}")
        else:
            self.passed += 1
            print(f"  {GREEN}✓{RESET} {label}")
        if os.environ.get("REPORT"):
            print(f"report: {label}\t{'failed' if failures else 'passed'}")

    def summary(self) -> None:
        total = self.passed + len(self.failed)
        print()
        if self.failed:
            print(f"{RED}✗ {self.passed}/{total} passed, {len(self.failed)} failed{RESET}")
        else:
            print(f"{GREEN}✓ {total}/{total} passed{RESET}")


class Runner(Results):
    def __init__(
        self,
        type_checker: list[str],
        interpreter: list[str] | None,
        python_mode: bool,
    ) -> None:
        super().__init__()
        self.type_checker = type_checker
        self.interpreter = interpreter  # None: tests not run
        self.python_mode = python_mode  # Suite checked against Python and mypy
        self.type_checked = 0
        self.run_only = 0

    def type_check(self, path: pathlib.Path, exit: Exit, error_expected: bool) -> list[str]:
        """Each test is checked in a separate directory, so other tests can't interfere. Single-module tests
        are copied to a new directory before running."""
        with tempfile.TemporaryDirectory() as tmp:
            checked = path if path.name == MAIN else pathlib.Path(shutil.copy(path, tmp))
            proc = run([*self.type_checker, str(checked)])
        output = proc.stdout + proc.stderr
        error = path.with_suffix(ERROR_EXPECTED)
        if proc.returncode != exit:
            first = output.strip().split("\n", 1)[0].replace(f"{checked.parent}/", "")
            return [f"check: exit {proc.returncode}, expected {int(exit)}: {first}"]
        if not error_expected:
            return []
        if not error.exists():
            return [f"check: missing {error.name}"]
        if error.read_text().strip() not in output:
            got = output.strip().replace(f"{checked.parent}/", "")
            return [f"check: expected {error.read_text().strip()!r}, got: {got}"]
        return []

    def type_check_accepts(self, test: pathlib.Path) -> list[str]:
        """Type-check a copy of a test in a temporary directory, so that the type checker writes nothing into
        the suite. The test must be accepted unless it is filed as a reported mypy bug."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / test.name
            if test.is_dir():
                shutil.copytree(test, copy)
                proc = run([*self.type_checker, MAIN], cwd=copy)
            else:
                shutil.copy(test, copy)
                proc = run([*self.type_checker, test.name], cwd=copy.parent)
        reported_bug = MYPY_BUG in test.parts
        if proc.returncode == 0 and reported_bug:
            return ["check: accepted, but filed as a reported mypy bug"]
        if proc.returncode != 0 and not reported_bug:
            return [f"check: rejected: {(proc.stdout + proc.stderr).strip().split(chr(10), 1)[0]}"]
        return []

    def interpret(self, path: pathlib.Path, outcome: PythonOutcome, undefined: bool) -> list[str]:
        if self.interpreter is None:
            return []
        succeeds = outcome == PythonOutcome.SUCCEEDS
        expected = path.with_suffix(EXPECTED)
        exception = path.with_suffix(EXCEPTION_EXPECTED)
        if expected.exists() == exception.exists():
            return [f"run: needs exactly one of {expected.name} and {exception.name}"]
        if succeeds != expected.exists():
            return [f"run: misfiled, has {expected.name if expected.exists() else exception.name}"]
        args_path = path.with_suffix(ARGS)
        args = args_path.read_text().splitlines() if args_path.exists() else []
        proc = run([*self.interpreter, path.name, *args], cwd=path.parent)
        if undefined and proc.returncode == Exit.UNDEFINED:
            return []
        if succeeds:
            status_path = path.with_suffix(STATUS_EXPECTED)
            status = int(status_path.read_text()) if status_path.exists() else 0
            if proc.returncode != status:
                return [f"run: exit {proc.returncode}, expected {status}: {proc.stderr.strip()}"]
            if proc.stdout != expected.read_text():
                return ["run: output mismatch"]
            return []
        name = exception.read_text().strip()
        if (outcome == PythonOutcome.REJECTS) != name.startswith(SYNTAX_ERROR):
            return [f"run: misfiled, expects {name}"]
        if proc.returncode == 0:
            return [f"run: expected {name} but script succeeded"]
        if name not in proc.stderr:
            return [f"run: expected {name}, got: {proc.stderr.strip()}"]
        output = path.with_suffix(OUTPUT_EXPECTED)
        if proc.stdout != (output.read_text() if output.exists() else ""):
            return ["run: output before the exception mismatch"]
        return []

    def run_test(self, suite: pathlib.Path, test: pathlib.Path) -> list[str]:
        """Run a test and return its failures. Within the suite, a test's path starts with its Python outcome
        and its PurePy outcome, as in python-succeeds/agrees/.../name.py, or .../name/main.py for a program of
        several modules."""
        dirs = test.relative_to(suite).parts[:-1]
        purepy = PurePyOutcome(dirs[1])
        exit, error_expected, python_outcome = expectation(PythonOutcome(dirs[0]), purepy)
        path = test / MAIN if test.is_dir() else test
        well_formed = exit == Exit.OK
        if self.python_mode:
            return [
                *(self.type_check_accepts(test) if well_formed else []),
                *self.interpret(path, python_outcome, False),
            ]
        undefined = purepy == PurePyOutcome.UNDEFINED
        return [
            *self.type_check(path, exit, error_expected),
            *(self.interpret(path, python_outcome, undefined) if well_formed else []),
        ]

    def run_suite(self, suite: pathlib.Path, jobs: int | None) -> None:
        """Tests run in parallel on jobs threads (default: one per core), reported in order."""
        found = list(tests(suite))
        self.type_checked = sum(
            1 for test in found if not self.python_mode or is_well_formed(suite, test)
        )
        self.run_only = len(found) - self.type_checked
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


def main(argv: Sequence[str] | None = None) -> None:
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
        "--jobs", type=int, help="number of tests run in parallel (default: number of cores)"
    )
    args = parser.parse_args(argv)
    runner = Runner(
        shlex.split(args.type_checker),
        None if args.no_run else shlex.split(args.interpreter),
        args.python_mode,
    )
    with suite() as path:
        runner.run_suite(path, args.jobs)
    runner.summary()
    if args.python_mode:
        print(
            f"Python mode: {runner.type_checked} tests type-checked and run, {runner.run_only} run only"
        )
    sys.exit(0 if not runner.failed else 1)


if __name__ == "__main__":
    main()
