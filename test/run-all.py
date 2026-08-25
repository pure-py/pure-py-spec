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

# Expected-output suffixes (module-level: sibling files of <test>.py)
EXPECTED = ".expected"
EXCEPTION_EXPECTED = f".exception{EXPECTED}"
ERROR_EXPECTED = f".error{EXPECTED}"
OUTPUT_EXPECTED = f".output{EXPECTED}"

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

RULE_NAME = re.compile(r"\\ruleName\{([a-z0-9-]+)\}")
CITATION = re.compile(r"# rule: ([a-z0-9-]+)")

# Checker entry points under src/
PARSE, CHECK, CHECK_PROGRAM = "syntax.py", "check_module.py", "check_program.py"

# Program-level test files (a test is a directory)
MAIN = "main.py"
EXPECTED_FILE, EXPECTED_EXIT, EXPECTED_ERROR = "expected", "expected_exit", "expected_error"

# PurePy exit codes (OK = accepted / ran clean)
class Exit(IntEnum):
    OK = 0
    PROHIBITED = 1   # syntax.py: prohibited syntactic form
    NOT_YET = 2      # syntax.py: planned, not yet supported
    ILL_FORMED = 3   # check_module.py: ill-formed

class Phase(StrEnum):
    PARSE = "parse"
    CHECK = "check"
    PYTHON = "python"
    RUN = "run"


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

    def expect_exit(self, cmd: list[str], expected: int, error_substr: str | None = None) -> None:
        phase = {PARSE: Phase.PARSE, CHECK: Phase.CHECK, CHECK_PROGRAM: Phase.CHECK}.get(
            pathlib.Path(cmd[1]).name, Phase.PYTHON)
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != expected:
            self._fail(phase, f"expected exit {expected}, got {proc.returncode}")
            return
        if error_substr is not None:
            output = proc.stdout + proc.stderr
            if error_substr not in output:
                self._fail(phase, f"expected output containing {error_substr!r}, got: {output.strip()}")

    def parse(self, path: pathlib.Path, expected: int, err: str | None = None) -> None:
        self.expect_exit(script_cmd(PARSE, path), expected, error_substr=err)

    def check(self, path: pathlib.Path, expected: int, err: str | None = None) -> None:
        self.expect_exit(script_cmd(CHECK, path), expected, error_substr=err)

    def python(self, path: pathlib.Path, expected: int = Exit.OK) -> None:
        self.expect_exit([self.interpreter, str(path)], expected)

    def _run(self, path: pathlib.Path, cwd: pathlib.Path | None) -> 'subprocess.CompletedProcess[str]':
        cmd_path = path.name if cwd is not None else str(path)
        return subprocess.run([self.interpreter, cmd_path], cwd=cwd, capture_output=True, text=True, check=False)

    def run_expecting_output(self, path: pathlib.Path, expected_path: pathlib.Path, cwd: pathlib.Path | None = None) -> None:
        phase = Phase.RUN
        proc = self._run(path, cwd)
        if proc.returncode != 0:
            self._fail(phase, f"exit {proc.returncode}: {proc.stderr.strip()}")
        elif proc.stdout != expected_path.read_text():
            self._fail(phase, "output mismatch")

    def run_expecting_exception(self, path: pathlib.Path, exception_path: pathlib.Path, cwd: pathlib.Path | None = None) -> None:
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

    def python_evidence(self, path: pathlib.Path, python_accepts: bool, expected_path: pathlib.Path, cwd: pathlib.Path | None = None) -> None:
        """Python must corroborate the verdict: run with the expected output
        (python_accepts) or raise the exception named in the sibling file. A
        test must carry the one piece of evidence and not the other."""
        exception_path = path.with_suffix(EXCEPTION_EXPECTED)
        if python_accepts:
            if exception_path.exists():
                self._fail(Phase.RUN, f"must not have {EXCEPTION_EXPECTED}")
            elif not expected_path.exists():
                self._fail(Phase.RUN, f"missing {expected_path.name}")
            else:
                self.run_expecting_output(path, expected_path, cwd=cwd)
        else:
            if expected_path.exists():
                self._fail(Phase.RUN, f"python-error must not have {expected_path.name}")
            elif not exception_path.exists():
                self._fail(Phase.RUN, f"missing {EXCEPTION_EXPECTED}")
            else:
                self.run_expecting_exception(path, exception_path, cwd=cwd)

    def run_multi_file_tests(self, category_root: pathlib.Path) -> None:
        """Each subdir is a test: main.py, expected_exit, plus fixtures and the
        Python-side evidence fixed by the verdict (the category directory name)."""
        python_accepts = category_root.name != Verdict.PYTHON_ERROR
        for d in sorted(p for p in category_root.rglob("*") if p.is_dir() and (p / MAIN).exists()):
            with self.test(d.relative_to(ROOT)):
                main_py = d / MAIN
                self.expect_exit(script_cmd(CHECK_PROGRAM, main_py),
                                 int((d / EXPECTED_EXIT).read_text().strip()),
                                 error_substr=substr(d / EXPECTED_ERROR))
                self.python_evidence(main_py, python_accepts,
                                     expected_path=d / EXPECTED_FILE, cwd=d)

    def module_test(self, p: pathlib.Path, module: pathlib.Path) -> None:
        """Assert a module-level test from its path: <verdict>[/<stage>].

        verdict in {semantically-valid, excluded, python-error} fixes how PurePy and
        Python must each respond; stage in {syntactic, static,
        dynamic} fixes where PurePy stops (dynamic = checker
        accepts, but evaluation is stuck)."""
        rel = p.relative_to(ROOT)
        with self.test(rel):
            dirs = p.parent.relative_to(module).parts
            err = substr(p.with_suffix(ERROR_EXPECTED))

            if dirs == (Verdict.SEMANTICALLY_VALID, Stage.PENDING):
                self.parse(p, Exit.NOT_YET)
                return
            if dirs[1:] == (Stage.STATIC, Stage.PENDING):
                self.parse(p, Exit.OK)
                self.check(p, Exit.OK)
                self.python_evidence(p, Verdict(dirs[0]) != Verdict.PYTHON_ERROR,
                                     expected_path=p.with_suffix(EXPECTED))
                return
            if dirs == (Verdict.PYTHON_ERROR, Stage.SYNTACTIC_ONLY):
                self.python(p)
                return

            verdict = Verdict(dirs[0])
            stage = Stage(dirs[1]) if len(dirs) > 1 and dirs[1] in {s.value for s in Stage} else None

            if verdict == Verdict.SEMANTICALLY_VALID:
                self.parse(p, Exit.OK)
                self.check(p, Exit.OK)
            elif stage == Stage.SYNTACTIC:
                self.parse(p, Exit.PROHIBITED, err)
            else:
                self.parse(p, Exit.OK)
                self.check(p, Exit.ILL_FORMED if stage == Stage.STATIC else Exit.OK,
                           err if stage == Stage.STATIC else None)

            if verdict != Verdict.PYTHON_ERROR and stage == Stage.SYNTACTIC:
                if p.with_suffix(EXCEPTION_EXPECTED).exists():
                    self._fail(Phase.RUN, f"must not have {EXCEPTION_EXPECTED}")
                else:
                    self.python(p)
            else:
                self.python_evidence(p, verdict != Verdict.PYTHON_ERROR,
                                     expected_path=p.with_suffix(EXPECTED))

    def summary(self) -> None:
        total = self.passed + self.failed
        print()
        if self.failed:
            print(f"{RED}✗ {self.passed}/{total} passed, {self.failed} failed{RESET}")
            sys.exit(1)
        print(f"{GREEN}✓ {total}/{total} passed{RESET}")


def check_rule_citations(r: Runner, base: pathlib.Path) -> None:
    """Every `# rule: X` in a test must name a rule the spec defines, so a
    citation cannot outlive the rule it points at."""
    spec = {m for f in sorted((ROOT / "spec").rglob("*.tex"))
            for m in RULE_NAME.findall(f.read_text(encoding="utf-8"))}
    stale = []
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        cited = CITATION.match(first)
        if cited is not None and cited.group(1) not in spec:
            stale.append(f"{path.relative_to(base)} cites {cited.group(1)}")
    if stale:
        r.bad("rule citations", "; ".join(stale))
    else:
        r.ok("rule citations")

def main() -> None:
    skip_mypy = "--no-mypy" in sys.argv
    if skip_mypy:
        sys.argv.remove("--no-mypy")
    interpreter = sys.argv[1] if len(sys.argv) > 1 else "python3"
    base = ROOT / "test"
    module = base / MODULE_LEVEL
    r = Runner(interpreter)

    print("cross-references")
    check_rule_citations(r, base)

    if not skip_mypy:
        print("mypy --strict src/")
        sources = sorted(str(p) for p in (ROOT / "src").glob("*.py")) + [str(ROOT / "test" / "run-all.py")]
        proc = subprocess.run(["mypy", "--strict", *sources], capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            r.ok("src/")
        else:
            r.bad("src/", proc.stdout.strip()[:400])

    last = None
    for p in sorted(module.rglob("*.py"), key=lambda p: (p.parent.as_posix(), p.name)):
        if HELPERS in p.parts:
            continue
        header = p.parent.relative_to(base)
        if header != last:
            print(header)
            last = header
        r.module_test(p, module)

    for verdict in Verdict:
        print(f"{PROGRAM_LEVEL}/{verdict}")
        r.run_multi_file_tests(base / PROGRAM_LEVEL / verdict)

    r.summary()


if __name__ == "__main__":
    main()
