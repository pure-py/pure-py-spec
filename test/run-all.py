#!/usr/bin/env python3
import argparse
import contextlib
import pathlib
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator
from enum import IntEnum, StrEnum
from typing import NamedTuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

EXPECTED = ".expected"
EXCEPTION_EXPECTED = f".exception{EXPECTED}"
ERROR_EXPECTED = f".error{EXPECTED}"
STATUS_EXPECTED = f".status{EXPECTED}"

MODULE_LEVEL, PROGRAM_LEVEL = "module-level", "program-level"
HELPERS = "helpers"
MAIN = "main.py"
MYPY_INI = "mypy.ini"
PYTHON_VERSION = (ROOT / ".python-version").read_text().strip()

RULE_NAME = re.compile(r"\\ruleName\{([a-z0-9-]+)\}")
RULE_DEF = re.compile(r"lab=\{\\ruleName\{([a-z0-9-]+)\}\}")
CITATION = re.compile(r"# rule: ([a-z0-9-]+)")

CHECK, CHECK_PROGRAM = "check_module.py", "check_program.py"


class Verdict(StrEnum):
    SEMANTICALLY_VALID = "semantically-valid"
    EXCLUDED = "excluded"
    PYTHON_ERROR = "python-error"


class Stage(StrEnum):
    SYNTACTIC = "syntactic"
    STATIC = "static"
    DYNAMIC = "dynamic"
    SYNTACTIC_ONLY = "syntactic-only"
    PENDING = "pending"


class Exit(IntEnum):
    OK = 0
    PROHIBITED = 1
    NOT_YET = 2
    ILL_FORMED = 3
    ILL_FORMED_PROGRAM = 4


class Expectation(NamedTuple):
    exit: Exit | None  # None: checker not run
    error_checked: bool  # checker output contains .error.expected
    python_accepts: bool | None  # None: not run under Python


EXPECTATIONS: dict[tuple[Verdict, Stage | None], Expectation] = {
    (Verdict.SEMANTICALLY_VALID, None): Expectation(Exit.OK, False, True),
    (Verdict.SEMANTICALLY_VALID, Stage.PENDING): Expectation(Exit.NOT_YET, False, None),
    (Verdict.EXCLUDED, Stage.SYNTACTIC): Expectation(Exit.PROHIBITED, True, True),
    (Verdict.EXCLUDED, Stage.STATIC): Expectation(Exit.ILL_FORMED, True, True),
    (Verdict.EXCLUDED, Stage.DYNAMIC): Expectation(Exit.OK, False, True),
    (Verdict.PYTHON_ERROR, Stage.SYNTACTIC): Expectation(Exit.PROHIBITED, True, False),
    (Verdict.PYTHON_ERROR, Stage.STATIC): Expectation(Exit.ILL_FORMED, True, False),
    (Verdict.PYTHON_ERROR, Stage.DYNAMIC): Expectation(Exit.OK, False, False),
    (Verdict.PYTHON_ERROR, Stage.SYNTACTIC_ONLY): Expectation(None, False, True),
}


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


class Runner:
    def __init__(self, interpreter: str | None, checker: list[str] | None) -> None:
        self.interpreter = interpreter  # None: tests not run
        self.checker = checker  # command given the test path; None: the reference checker
        self.passed = 0
        self.failed: list[str] = []
        self.skipped: list[str] = []
        self.failures: list[str] = []

    @contextlib.contextmanager
    def test(self, label: object) -> Iterator[None]:
        self.failures = []
        yield
        if self.failures:
            self.failed.append(f"{label} ({'; '.join(self.failures)})")
            print(f"  {RED}✗{RESET} {self.failed[-1]}")
        else:
            self.passed += 1
            print(f"  {GREEN}✓{RESET} {label}")

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def check(self, path: pathlib.Path, program: bool, exit: Exit, error_checked: bool) -> None:
        reference = ["python3", str(ROOT / "src" / (CHECK_PROGRAM if program else CHECK))]
        proc = run([*(self.checker or reference), str(path)])
        exits = {exit, Exit.ILL_FORMED_PROGRAM} if program and exit == Exit.ILL_FORMED else {exit}
        if proc.returncode not in exits:
            output = (proc.stdout + proc.stderr).strip().split("\n", 1)[0]
            self.fail(
                f"check: exit {proc.returncode}, expected {sorted(map(int, exits))}: {output}"
            )
        elif error_checked and self.checker is None:  # messages are the reference checker's
            error = path.with_suffix(ERROR_EXPECTED)
            output = proc.stdout + proc.stderr
            if not error.exists():
                self.fail(f"check: missing {error.name}")
            elif error.read_text().strip() not in output:
                self.fail(f"check: expected {error.read_text().strip()!r}, got: {output.strip()}")

    def python(self, path: pathlib.Path, accepts: bool) -> None:
        assert self.interpreter is not None
        expected = path.with_suffix(EXPECTED)
        exception = path.with_suffix(EXCEPTION_EXPECTED)
        if expected.exists() == exception.exists():
            self.fail(f"run: needs exactly one of {expected.name} and {exception.name}")
            return
        if accepts != expected.exists():
            self.fail(
                f"run: misfiled, has {expected.name if expected.exists() else exception.name}"
            )
            return
        proc = run([self.interpreter, path.name], cwd=path.parent)
        if accepts:
            status_path = path.with_suffix(STATUS_EXPECTED)
            status = int(status_path.read_text()) if status_path.exists() else 0
            if proc.returncode != status:
                self.fail(f"run: exit {proc.returncode}, expected {status}: {proc.stderr.strip()}")
            elif proc.stdout != expected.read_text():
                self.fail("run: output mismatch")
        else:
            name = exception.read_text().strip()
            if proc.returncode == 0:
                self.fail(f"run: expected {name} but script succeeded")
            elif name not in proc.stderr:
                self.fail(f"run: expected {name}, got: {proc.stderr.strip()}")

    def run_test(self, test: pathlib.Path, program: bool) -> None:
        """Path under tier: <verdict>[/<stage>]/.../<test>.py or .../<test>/main.py (program)."""
        dirs = test.relative_to(TEST).parts[1:-1]
        verdict = Verdict(dirs[0])
        stage = Stage(dirs[1]) if len(dirs) > 1 and dirs[1] in Stage else None
        if stage == Stage.PENDING and self.checker is not None:
            # spec doesn't define pending forms, so only the reference checker is held to them
            self.skipped.append(str(test.relative_to(ROOT)))
            return
        with self.test(test.relative_to(ROOT)):
            exit, error_checked, python_accepts = EXPECTATIONS[verdict, stage]
            path = test / MAIN if program else test
            if exit is not None:
                self.check(path, program, exit, error_checked)
            if python_accepts is not None and self.interpreter is not None:
                self.python(path, python_accepts)

    def summary(self) -> None:
        total = self.passed + len(self.failed)
        print()
        if self.skipped:
            print(f"{len(self.skipped)} pending tests skipped: {', '.join(self.skipped)}")
        if self.failed:
            print(f"{RED}✗ {self.passed}/{total} passed, {len(self.failed)} failed{RESET}")
        else:
            print(f"{GREEN}✓ {total}/{total} passed{RESET}")


def compare_known_failures(failed: list[str], known_failures: pathlib.Path, update: bool) -> bool:
    """Whether the failures are exactly those listed; with update, rewrite the list instead."""
    if update:
        known_failures.write_text("".join(line + "\n" for line in sorted(failed)))
        print(f"{len(failed)} failures written to {known_failures}")
        return True
    known = set(known_failures.read_text().splitlines()) if known_failures.exists() else set()
    for line in sorted(set(failed) - known):
        print(f"{RED}unexpected:{RESET} {line}")
    for line in sorted(known - set(failed)):
        print(f"{GREEN}fixed:{RESET} {line}")
    if set(failed) != known:
        print(f"{RED}✗ {known_failures} out of date; rerun with --update{RESET}")
        return False
    print(f"{GREEN}✓ failures as listed in {known_failures}{RESET}")
    return True


def tests() -> Iterator[tuple[pathlib.Path, bool]]:
    """Tests of both tiers in path order, each with whether it is a program."""
    for tier, program in ((MODULE_LEVEL, False), (PROGRAM_LEVEL, True)):
        found = (TEST / tier).rglob(MAIN if program else "*.py")
        paths = [
            path.parent if program else path
            for path in found
            if HELPERS not in path.parts and "__pycache__" not in path.parts
        ]
        for test in sorted(paths, key=lambda test: (test.parent.as_posix(), test.name)):
            yield test, program


def check_unique_rule_names(r: Runner) -> None:
    with r.test("unique rule names"):
        where: dict[str, list[str]] = {}
        for source in ("spec", "paper"):
            for f in sorted((ROOT / source).rglob("*.tex")):
                for name in RULE_DEF.findall(f.read_text(encoding="utf-8")):
                    where.setdefault(name, []).append(str(f.relative_to(ROOT)))
        for name, files in sorted(where.items()):
            if len(files) > 1:
                r.fail(f"{name} in {', '.join(files)}")


def check_rule_attribution(r: Runner) -> None:
    with r.test("rule attribution"):
        spec = {
            m
            for f in sorted((ROOT / "spec").rglob("*.tex"))
            for m in RULE_NAME.findall(f.read_text(encoding="utf-8"))
        }
        for path in sorted(TEST.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            cited = CITATION.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
            if cited is not None and cited.group(1) not in spec:
                r.fail(f"{path.relative_to(TEST)} cites {cited.group(1)}")


def check_lint(r: Runner) -> None:
    with r.test("checker type-checks"):
        sources = sorted(str(path) for path in (ROOT / "src").glob("*.py")) + [
            str(TEST / "run-all.py")
        ]
        for tool in (
            ["mypy", "--strict", "--python-version", PYTHON_VERSION],
            ["ruff", "check"],
            ["ruff", "format", "--check"],
        ):
            proc = run([*tool, *sources])
            if proc.returncode != 0:
                r.fail((proc.stdout + proc.stderr).strip()[:400])
                break


def check_mypy_compatibility(r: Runner) -> None:
    with r.test("mypy compatibility"):
        paths = [
            path
            for path in sorted((TEST / MODULE_LEVEL / Verdict.SEMANTICALLY_VALID).rglob("*.py"))
            if Stage.PENDING not in path.parts
        ]
        # mypy reports paths relative to its working directory
        relative = [str(path.relative_to(ROOT)) for path in paths]
        proc = run(
            [
                "mypy",
                "--python-version",
                PYTHON_VERSION,
                "--config-file",
                str(pathlib.Path("test") / MYPY_INI),
                "--no-error-summary",
                "--no-color-output",
                *relative,
            ],
            cwd=ROOT,
        )
        rejected = {
            line.split(":", 1)[0] for line in proc.stdout.splitlines() if ": error:" in line
        }
        for path in sorted(rejected):
            r.fail(f"{path} rejected by mypy")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("interpreter", nargs="?", default="python3")
    parser.add_argument("--no-mypy", action="store_true")
    parser.add_argument(
        "--no-run", action="store_true", help="check the tests without running them"
    )
    parser.add_argument(
        "--checker",
        help="command run on the path of each test in place of src/, with the same exit codes; "
        "error messages are not compared and pending tests are skipped",
    )
    parser.add_argument(
        "--known-failures",
        type=pathlib.Path,
        help="file listing the expected failures; the run passes if its failures are exactly these",
    )
    parser.add_argument(
        "--update", action="store_true", help="rewrite the known failures file from this run"
    )
    args = parser.parse_args()
    r = Runner(
        None if args.no_run else args.interpreter,
        shlex.split(args.checker) if args.checker else None,
    )

    print("cross-references")
    check_unique_rule_names(r)
    check_rule_attribution(r)

    if not args.no_mypy:
        print("mypy and ruff over src/")
        check_lint(r)
        check_mypy_compatibility(r)

    last = None
    for test, program in tests():
        header = test.parent.relative_to(TEST)
        if header != last:
            print(header)
            last = header
        r.run_test(test, program)

    r.summary()
    ok = not r.failed
    if args.known_failures is not None:
        ok = compare_known_failures(r.failed, args.known_failures, args.update)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
