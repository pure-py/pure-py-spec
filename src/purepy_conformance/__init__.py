import argparse
import concurrent.futures
import contextlib
import importlib.resources
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
    UNDEFINED = "undefined"
    AGREES = "agrees"


SYNTAX_ERROR = "SyntaxError"


class Exit(IntEnum):
    OK = 0
    NOT_ALLOWED = 1
    ILL_FORMED = 3


class Expectation(NamedTuple):
    exit: Exit
    error_checked: bool  # type checker output contains .error.expected
    python: PythonOutcome


# Type checker verdict for each PurePy outcome
TYPE_CHECKER: dict[PurePyOutcome, tuple[Exit, bool]] = {
    PurePyOutcome.PARSER_REJECTS: (Exit.NOT_ALLOWED, True),
    PurePyOutcome.TYPING_REJECTS: (Exit.ILL_FORMED, True),
    PurePyOutcome.UNDEFINED: (Exit.OK, False),
    PurePyOutcome.AGREES: (Exit.OK, False),
}


def expectation(python: PythonOutcome, purepy: PurePyOutcome) -> Expectation:
    exit, error_checked = TYPE_CHECKER[purepy]
    return Expectation(exit, error_checked, python)


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

    def summary(self) -> None:
        total = self.passed + len(self.failed)
        print()
        if self.failed:
            print(f"{RED}✗ {self.passed}/{total} passed, {len(self.failed)} failed{RESET}")
        else:
            print(f"{GREEN}✓ {total}/{total} passed{RESET}")


class Runner(Results):
    def __init__(self, type_checker: list[str], interpreter: str | None, python: bool) -> None:
        super().__init__()
        self.type_checker = type_checker
        self.interpreter = interpreter  # None: tests not run
        self.python = python  # Implementation under test is Python itself
        self.type_checked = 0
        self.run_only = 0

    def check(self, path: pathlib.Path, exit: Exit, error_checked: bool) -> list[str]:
        """Each test is checked in a separate directory, so other tests can't interfere. Single-module tests
        are copied to a new directory before running."""
        with tempfile.TemporaryDirectory() as alone:
            checked = path if path.name == MAIN else pathlib.Path(shutil.copy(path, alone))
            proc = run([*self.type_checker, str(checked)])
        output = proc.stdout + proc.stderr
        error = path.with_suffix(ERROR_EXPECTED)
        if proc.returncode != exit:
            first = output.strip().split("\n", 1)[0].replace(f"{checked.parent}/", "")
            return [f"check: exit {proc.returncode}, expected {int(exit)}: {first}"]
        if not error_checked:
            return []
        if not error.exists():
            return [f"check: missing {error.name}"]
        if error.read_text().strip() not in output:
            got = output.strip().replace(f"{checked.parent}/", "")
            return [f"check: expected {error.read_text().strip()!r}, got: {got}"]
        return []

    def accepts(self, test: pathlib.Path) -> list[str]:
        """Failures of the type checker to accept a test, a module or the directory of a program, or to
        reject it if the test is filed under a reported mypy bug. The test is copied to a new directory and
        checked from there, so that its modules resolve and nothing is written into the suite."""
        with tempfile.TemporaryDirectory() as alone:
            copy = pathlib.Path(alone) / test.name
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

    def run_python(self, path: pathlib.Path, outcome: PythonOutcome) -> list[str]:
        assert self.interpreter is not None
        accepts = outcome == PythonOutcome.SUCCEEDS
        expected = path.with_suffix(EXPECTED)
        exception = path.with_suffix(EXCEPTION_EXPECTED)
        if expected.exists() == exception.exists():
            return [f"run: needs exactly one of {expected.name} and {exception.name}"]
        if accepts != expected.exists():
            return [f"run: misfiled, has {expected.name if expected.exists() else exception.name}"]
        args_path = path.with_suffix(ARGS)
        args = args_path.read_text().splitlines() if args_path.exists() else []
        proc = run([self.interpreter, path.name, *args], cwd=path.parent)
        if accepts:
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
        """Failures of a test at a path below suite: <Python outcome>/<PurePy outcome>[/<subset>]/...
        /<test>.py, or .../<test>/main.py for a program of several modules."""
        dirs = test.relative_to(suite).parts[:-1]
        exit, error_checked, python = expectation(PythonOutcome(dirs[0]), PurePyOutcome(dirs[1]))
        path = test / MAIN if test.is_dir() else test
        if self.python:
            return [
                *(self.accepts(test) if exit == Exit.OK else []),
                *(self.run_python(path, python) if self.interpreter is not None else []),
            ]
        return [
            *self.check(path, exit, error_checked),
            *(self.run_python(path, python) if self.interpreter is not None else []),
        ]

    def run_suite(self, suite: pathlib.Path, jobs: int | None) -> None:
        """Tests run in parallel on jobs threads (default: one per core), reported in order."""
        found = list(tests(suite))
        self.type_checked = sum(1 for test in found if not self.python or well_formed(suite, test))
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


def well_formed(suite: pathlib.Path, test: pathlib.Path) -> bool:
    return TYPE_CHECKER[PurePyOutcome(test.relative_to(suite).parts[1])][0] == Exit.OK


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
        "--python",
        action="store_true",
        help="test Python itself: run every test, and type-check only the tests well-formed in PurePy, which must be accepted",
    )
    parser.add_argument(
        "--jobs", type=int, help="number of tests run in parallel (default: number of cores)"
    )
    args = parser.parse_args(argv)
    r = Runner(
        shlex.split(args.type_checker), None if args.no_run else args.interpreter, args.python
    )
    with suite() as path:
        r.run_suite(path, args.jobs)
    r.summary()
    if args.python:
        print(f"Python mode: {r.type_checked} tests type-checked and run, {r.run_only} run only")
    sys.exit(0 if not r.failed else 1)


if __name__ == "__main__":
    main()
