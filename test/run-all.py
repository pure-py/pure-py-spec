#!/usr/bin/env python3
"""PurePy test runner.

Walks the test directories, runs each test through the appropriate steps
(parse, check, run) and reports pass/fail counts.
"""

import contextlib
import pathlib
import re
import subprocess
import sys
from collections.abc import Iterator
from enum import IntEnum, StrEnum

ROOT = pathlib.Path(__file__).resolve().parent.parent
GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

# Expected-output suffixes: sibling files of <test>.py, or of main.py for a program-level test
EXPECTED = ".expected"
EXCEPTION_EXPECTED = f".exception{EXPECTED}"
ERROR_EXPECTED = f".error{EXPECTED}"
OUTPUT_EXPECTED = f".output{EXPECTED}"
STATUS_EXPECTED = f".status{EXPECTED}"  # exit status when nonzero

# Tier directory names
MODULE_LEVEL, PROGRAM_LEVEL = "module-level", "program-level"


# Verdict / stage directory names: a test's path is its specification
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


HELPERS = "helpers"
MYPY_INI = "mypy.ini"
PYTHON_VERSION = (ROOT / ".python-version").read_text().strip()

RULE_NAME = re.compile(r"\\ruleName\{([a-z0-9-]+)\}")
RULE_DEF = re.compile(r"lab=\{\\ruleName\{([a-z0-9-]+)\}\}")
CITATION = re.compile(r"# rule: ([a-z0-9-]+)")

# Checker entry points under src/
CHECK, CHECK_PROGRAM = "check_module.py", "check_program.py"

# Entry module of a program-level test (a test is a directory)
MAIN = "main.py"


# PurePy exit codes (OK = accepted / ran clean)
class Exit(IntEnum):
    OK = 0
    PROHIBITED = 1  # prohibited syntactic form
    NOT_YET = 2  # planned, not yet supported
    ILL_FORMED = 3  # ill-formed module
    ILL_FORMED_PROGRAM = 4  # ill-formed program, such as an import cycle


class Phase(StrEnum):
    CHECK = "check"
    PYTHON = "python"
    RUN = "run"


# Expected outcomes by verdict and stage: checker exit status, whether the checker's
# message must match .error.expected, and whether Python accepts the test (None: not run)
EXPECTATIONS: dict[tuple[Verdict, Stage | None], tuple[Exit, bool, bool | None]] = {
    (Verdict.SEMANTICALLY_VALID, None): (Exit.OK, False, True),
    (Verdict.SEMANTICALLY_VALID, Stage.PENDING): (Exit.NOT_YET, False, None),
    (Verdict.EXCLUDED, Stage.SYNTACTIC): (Exit.PROHIBITED, True, True),
    (Verdict.EXCLUDED, Stage.STATIC): (Exit.ILL_FORMED, True, True),
    (Verdict.EXCLUDED, Stage.DYNAMIC): (Exit.OK, False, True),
    (Verdict.PYTHON_ERROR, Stage.SYNTACTIC): (Exit.PROHIBITED, True, False),
    (Verdict.PYTHON_ERROR, Stage.STATIC): (Exit.ILL_FORMED, True, False),
    (Verdict.PYTHON_ERROR, Stage.DYNAMIC): (Exit.OK, False, False),
}


def script_cmd(script: str, path: pathlib.Path) -> list[str]:
    return ["python3", str(ROOT / "src" / script), str(path)]


def substr(path: pathlib.Path) -> str | None:
    return path.read_text().strip() if path.exists() else None


class Runner:
    def __init__(self, interpreter: str) -> None:
        self.interpreter = interpreter
        self.passed = 0
        self.failed = 0
        self._failures: list[str] = []

    def ok(self, label: object) -> None:
        self.passed += 1
        print(f"  {GREEN}✓{RESET} {label}")

    def bad(self, label: object, msg: str) -> None:
        self.failed += 1
        print(f"  {RED}✗{RESET} {label} ({msg})")

    @contextlib.contextmanager
    def test(self, label: object) -> Iterator[None]:
        """Group a test's phases into one result: a single pass line if every
        phase passes, else a single fail line listing the phases that failed."""
        self._failures = []
        try:
            yield
        finally:
            if self._failures:
                self.bad(label, "; ".join(self._failures))
            else:
                self.ok(label)

    def _fail(self, phase: Phase, msg: str) -> None:
        self._failures.append(f"{phase}: {msg}")

    def expect_exit(
        self,
        cmd: list[str],
        expected: set[int],
        error_substr: str | None = None,
        cwd: pathlib.Path | None = None,
    ) -> None:
        phase = {
            CHECK: Phase.CHECK,
            CHECK_PROGRAM: Phase.CHECK,
        }.get(pathlib.Path(cmd[1]).name, Phase.PYTHON)
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd)
        if proc.returncode not in expected:
            self._fail(phase, f"expected exit {sorted(expected)}, got {proc.returncode}")
            return
        if error_substr is not None:
            output = proc.stdout + proc.stderr
            if error_substr not in output:
                self._fail(
                    phase,
                    f"expected output containing {error_substr!r}, got: {output.strip()}",
                )

    def python(self, path: pathlib.Path, cwd: pathlib.Path | None = None) -> None:
        cmd_path = path.name if cwd is not None else str(path)
        self.expect_exit([self.interpreter, cmd_path], {Exit.OK}, cwd=cwd)

    def _run(
        self, path: pathlib.Path, cwd: pathlib.Path | None
    ) -> "subprocess.CompletedProcess[str]":
        cmd_path = path.name if cwd is not None else str(path)
        return subprocess.run(
            [self.interpreter, cmd_path],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_expecting_output(
        self,
        path: pathlib.Path,
        expected_path: pathlib.Path,
        status_path: pathlib.Path,
        cwd: pathlib.Path | None = None,
    ) -> None:
        phase = Phase.RUN
        proc = self._run(path, cwd)
        status = int(status_path.read_text()) if status_path.exists() else 0
        if proc.returncode != status:
            self._fail(phase, f"exit {proc.returncode}, expected {status}: {proc.stderr.strip()}")
        elif proc.stdout != expected_path.read_text():
            self._fail(phase, "output mismatch")

    def run_expecting_exception(
        self,
        path: pathlib.Path,
        exception_path: pathlib.Path,
        cwd: pathlib.Path | None = None,
    ) -> None:
        phase = Phase.RUN
        expected = exception_path.read_text().strip()
        proc = self._run(path, cwd)
        if proc.returncode == 0:
            self._fail(phase, f"expected {expected} but script succeeded")
        elif expected not in proc.stderr:
            self._fail(phase, f"expected {expected}, got: {proc.stderr.strip()}")
        output_path = path.with_suffix(OUTPUT_EXPECTED)
        if output_path.exists() and proc.stdout != output_path.read_text():
            self._fail(phase, f"output before {expected} mismatch")

    def python_evidence(
        self,
        path: pathlib.Path,
        python_accepts: bool,
        expected_path: pathlib.Path,
        status_path: pathlib.Path,
        cwd: pathlib.Path | None = None,
    ) -> None:
        """Python corroborates the verdict. If python_accepts, output must match .expected
        (exit status .status.expected if present) and .exception.expected must be absent;
        otherwise run must raise exception named in .exception.expected and .expected must
        be absent."""
        exception_path = path.with_suffix(EXCEPTION_EXPECTED)
        if python_accepts:
            if exception_path.exists():
                self._fail(Phase.RUN, f"must not have {EXCEPTION_EXPECTED}")
            elif not expected_path.exists():
                self._fail(Phase.RUN, f"missing {expected_path.name}")
            else:
                self.run_expecting_output(path, expected_path, status_path, cwd=cwd)
        else:
            if expected_path.exists():
                self._fail(Phase.RUN, f"python-error must not have {expected_path.name}")
            elif not exception_path.exists():
                self._fail(Phase.RUN, f"missing {EXCEPTION_EXPECTED}")
            else:
                self.run_expecting_exception(path, exception_path, cwd=cwd)

    def run_test(self, path: pathlib.Path, tier: pathlib.Path, program: bool) -> None:
        """A test's path under its tier is its specification: <verdict>[/<stage>]/.../<test>.
        A program-level test is the directory of its main.py, checked as a program and run
        from that directory; its expectations are siblings of main.py."""
        test_dir = path.parent if program else None
        with self.test((path.parent if program else path).relative_to(ROOT)):
            dirs = (path.parent.parent if program else path.parent).relative_to(tier).parts
            verdict = Verdict(dirs[0])
            stage = Stage(dirs[1]) if len(dirs) > 1 and dirs[1] in Stage else None
            if stage == Stage.SYNTACTIC_ONLY:
                self.python(path, cwd=test_dir)
                return
            status, message_checked, python_accepts = EXPECTATIONS[verdict, stage]
            err = substr(path.with_suffix(ERROR_EXPECTED)) if message_checked else None
            statuses = {int(status)}
            if program and status == Exit.ILL_FORMED:
                statuses.add(Exit.ILL_FORMED_PROGRAM)
            self.expect_exit(
                script_cmd(CHECK_PROGRAM if program else CHECK, path), statuses, error_substr=err
            )
            if python_accepts is None:
                return
            if stage == Stage.SYNTACTIC and python_accepts:
                if path.with_suffix(EXCEPTION_EXPECTED).exists():
                    self._fail(Phase.RUN, f"must not have {EXCEPTION_EXPECTED}")
                else:
                    self.python(path, cwd=test_dir)
            else:
                self.python_evidence(
                    path,
                    python_accepts,
                    expected_path=path.with_suffix(EXPECTED),
                    status_path=path.with_suffix(STATUS_EXPECTED),
                    cwd=test_dir,
                )

    def summary(self) -> None:
        total = self.passed + self.failed
        print()
        if self.failed:
            print(f"{RED}✗ {self.passed}/{total} passed, {self.failed} failed{RESET}")
            sys.exit(1)
        print(f"{GREEN}✓ {total}/{total} passed{RESET}")


def check_unique_rule_names(r: Runner) -> None:
    where: dict[str, list[str]] = {}
    for source in ("spec", "paper"):
        for f in sorted((ROOT / source).rglob("*.tex")):
            for name in RULE_DEF.findall(f.read_text(encoding="utf-8")):
                where.setdefault(name, []).append(str(f.relative_to(ROOT)))
    duplicates = [
        f"{name} in {', '.join(files)}" for name, files in sorted(where.items()) if len(files) > 1
    ]
    if duplicates:
        r.bad("unique rule names", "; ".join(duplicates))
    else:
        r.ok("unique rule names")


def check_rule_attribution(r: Runner, base: pathlib.Path) -> None:
    spec = {
        m
        for f in sorted((ROOT / "spec").rglob("*.tex"))
        for m in RULE_NAME.findall(f.read_text(encoding="utf-8"))
    }
    stale = []
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        cited = CITATION.match(first)
        if cited is not None and cited.group(1) not in spec:
            stale.append(f"{path.relative_to(base)} cites {cited.group(1)}")
    if stale:
        r.bad("rule attribution", "; ".join(stale))
    else:
        r.ok("rule attribution")


def check_mypy_compatibility(r: Runner, module: pathlib.Path) -> None:
    paths = [
        path
        for path in sorted((module / Verdict.SEMANTICALLY_VALID).rglob("*.py"))
        if Stage.PENDING not in path.parts
    ]
    # mypy reports paths relative to its working directory
    relative = [path.relative_to(ROOT) for path in paths]
    proc = subprocess.run(
        [
            "mypy",
            "--python-version",
            PYTHON_VERSION,
            "--config-file",
            str(pathlib.Path("test") / MYPY_INI),
            "--no-error-summary",
            "--no-color-output",
            *(str(path) for path in relative),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    rejected = {line.split(":", 1)[0] for line in proc.stdout.splitlines() if ": error:" in line}
    if rejected:
        r.bad(
            "mypy compatibility", "; ".join(f"{path} rejected by mypy" for path in sorted(rejected))
        )
    else:
        r.ok("mypy compatibility")


def main() -> None:
    skip_mypy = "--no-mypy" in sys.argv
    if skip_mypy:
        sys.argv.remove("--no-mypy")
    interpreter = sys.argv[1] if len(sys.argv) > 1 else "python3"
    base = ROOT / "test"
    module = base / MODULE_LEVEL
    r = Runner(interpreter)

    print("cross-references")
    check_unique_rule_names(r)
    check_rule_attribution(r, base)

    if not skip_mypy:
        print("mypy and ruff over src/")
        sources = sorted(str(path) for path in (ROOT / "src").glob("*.py")) + [
            str(ROOT / "test" / "run-all.py")
        ]
        for tool in (
            ["mypy", "--strict", "--python-version", PYTHON_VERSION],
            ["ruff", "check"],
            ["ruff", "format", "--check"],
        ):
            proc = subprocess.run([*tool, *sources], capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                r.bad("checker type-checks", (proc.stdout + proc.stderr).strip()[:400])
                break
        else:
            r.ok("checker type-checks")
        check_mypy_compatibility(r, module)

    for tier, program in ((module, False), (base / PROGRAM_LEVEL, True)):
        last = None
        for path in sorted(
            tier.rglob(MAIN if program else "*.py"),
            key=lambda path: (path.parent.as_posix(), path.name),
        ):
            if HELPERS in path.parts or "__pycache__" in path.parts:
                continue
            header = (path.parent.parent if program else path.parent).relative_to(base)
            if header != last:
                print(header)
                last = header
            r.run_test(path, tier, program)

    r.summary()


if __name__ == "__main__":
    main()
