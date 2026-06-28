#!/usr/bin/env python3
"""PurePy test runner.

Walks the test directories, runs each test through the appropriate steps
(parse, check, run) and reports pass/fail counts.
"""

import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

# Expected-output suffixes (module-level: sibling files of <test>.py)
EXPECTED = ".expected"
EXCEPTION_EXPECTED = f".exception{EXPECTED}"
ERROR_EXPECTED = f".error{EXPECTED}"

# Verdict / stage directory names: a test's path is its specification
WELL_FORMED, UNSUPPORTED, ILL_FORMED = "well-formed", "unsupported", "ill-formed"
SYNTACTIC, SEMANTIC, SYNTACTIC_ONLY = "syntactic", "semantic", "syntactic-only"
PENDING, HELPERS = "pending", "helpers"

# Checker entry points under src/
PARSE, CHECK, CHECK_PROGRAM = "parse.py", "check_module.py", "check_program.py"

# Program-level test files (a test is a directory)
MAIN = "main.py"
EXPECTED_FILE, EXPECTED_EXIT, EXPECTED_ERROR = "expected", "expected_exit", "expected_error"

# PurePy non-zero exit codes (0 = accepted / ran clean)
REJECT_PARSE = 1   # parse.py: unsupported syntactic form
NOT_YET = 2        # parse.py: planned, not yet supported
REJECT_CHECK = 3   # check_module.py: ill-formed


def script_cmd(script, path):
    return ["python3", str(ROOT / "src" / script), str(path)]


class Runner:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def ok(self, label):
        self.passed += 1
        print(f"  {GREEN}✓{RESET} {label}")

    def bad(self, label, msg):
        self.failed += 1
        print(f"  {RED}✗{RESET} {label} ({msg})")

    def expect_exit(self, label, cmd, expected, error_substr=None):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != expected:
            self.bad(label, f"expected exit {expected}, got {proc.returncode}")
            return
        if error_substr is not None:
            output = proc.stdout + proc.stderr
            if error_substr not in output:
                self.bad(label, f"expected output containing {error_substr!r}, got: {output.strip()}")
                return
        self.ok(label)

    def run_python(self, label, interpreter, path, cwd=None, expected_path=None):
        """Run a script under Python; compare stdout to expected_path, or check
        stderr for the class named in the .exception.expected sibling."""
        if expected_path is None:
            expected_path = path.with_suffix(EXPECTED)
        exception_path = path.with_suffix(EXCEPTION_EXPECTED)
        cmd_path = path.name if cwd is not None else str(path)
        proc = subprocess.run([interpreter, cmd_path], cwd=cwd, capture_output=True, text=True)

        if exception_path.exists():
            expected = exception_path.read_text().strip()
            if proc.returncode == 0:
                self.bad(label, f"expected {expected} but script succeeded")
            elif expected not in proc.stderr:
                self.bad(label, f"expected {expected}, got: {proc.stderr.strip()}")
            else:
                self.ok(label)
            return

        if proc.returncode != 0:
            self.bad(label, f"exit {proc.returncode}: {proc.stderr.strip()}")
            return
        if proc.stdout != expected_path.read_text():
            self.bad(label, "output mismatch")
        else:
            self.ok(label)

    def run_multi_file_tests(self, category_root, interpreter):
        """Each subdir is a test: main.py, expected_exit, plus optional fixtures and expected file."""
        for d in sorted(p for p in category_root.iterdir() if p.is_dir()):
            rel = d.relative_to(ROOT)
            main_py = d / MAIN
            expected_exit_code = int((d / EXPECTED_EXIT).read_text().strip())
            err_path = d / EXPECTED_ERROR
            err_substr = err_path.read_text().strip() if err_path.exists() else None
            self.expect_exit(f"{rel} (check)", script_cmd(CHECK_PROGRAM, main_py), expected_exit_code, error_substr=err_substr)
            expected_path = d / EXPECTED_FILE
            if expected_path.exists():
                self.run_python(f"{rel} (run)", interpreter, main_py, cwd=d, expected_path=expected_path)

    def module_test(self, p, module, interpreter):
        """Assert a module-level test from its path: <verdict>[/<stage>].

        verdict in {well-formed, unsupported, ill-formed} fixes how PurePy and
        CPython must each respond; stage in {syntactic, semantic} fixes where
        PurePy rejects. unsupported vs ill-formed is marked by whether CPython
        accepts (.expected) or rejects (.exception.expected).
        """
        rel = p.relative_to(ROOT)
        dirs = p.parent.relative_to(module).parts
        has_expected = p.with_suffix(EXPECTED).exists()
        has_exception = p.with_suffix(EXCEPTION_EXPECTED).exists()
        err_file = p.with_suffix(ERROR_EXPECTED)
        err = err_file.read_text().strip() if err_file.exists() else None

        if dirs == (WELL_FORMED, PENDING):
            self.expect_exit(str(rel), script_cmd(PARSE, p), NOT_YET)
            return
        if dirs == (ILL_FORMED, SEMANTIC, PENDING):
            self.expect_exit(f"{rel} (parse)", script_cmd(PARSE, p), 0)
            self.expect_exit(f"{rel} (check)", script_cmd(CHECK, p), 0)
            self.run_python(f"{rel} (run)", interpreter, p)
            return
        if dirs == (ILL_FORMED, SYNTACTIC_ONLY):
            self.expect_exit(str(rel), [interpreter, str(p)], 0)
            return

        verdict = dirs[0]
        stage = dirs[1] if len(dirs) > 1 else None

        if verdict == WELL_FORMED:
            self.expect_exit(f"{rel} (parse)", script_cmd(PARSE, p), 0)
            self.expect_exit(f"{rel} (check)", script_cmd(CHECK, p), 0)
        elif stage == SYNTACTIC:
            self.expect_exit(f"{rel} (parse)", script_cmd(PARSE, p), REJECT_PARSE, error_substr=err)
        elif stage == SEMANTIC:
            self.expect_exit(f"{rel} (parse)", script_cmd(PARSE, p), 0)
            self.expect_exit(f"{rel} (check)", script_cmd(CHECK, p), REJECT_CHECK, error_substr=err)

        if verdict in (WELL_FORMED, UNSUPPORTED):
            if has_exception:
                self.bad(f"{rel} (run)", f"must not have {EXCEPTION_EXPECTED}")
            elif stage == SYNTACTIC:
                self.expect_exit(f"{rel} (python)", [interpreter, str(p)], 0)
            elif not has_expected:
                self.bad(f"{rel} (run)", f"missing {EXPECTED}")
            else:
                self.run_python(f"{rel} (run)", interpreter, p)
        else:
            if has_expected:
                self.bad(f"{rel} (run)", f"ill-formed must not have {EXPECTED}")
            elif not has_exception:
                self.bad(f"{rel} (run)", f"missing {EXCEPTION_EXPECTED}")
            else:
                self.run_python(f"{rel} (run)", interpreter, p)

    def summary(self):
        total = self.passed + self.failed
        print()
        if self.failed:
            print(f"{RED}✗ {self.passed}/{total} passed, {self.failed} failed{RESET}")
            sys.exit(1)
        print(f"{GREEN}✓ {total}/{total} passed{RESET}")


def main():
    skip_mypy = "--no-mypy" in sys.argv
    if skip_mypy:
        sys.argv.remove("--no-mypy")
    interpreter = sys.argv[1] if len(sys.argv) > 1 else "python3"
    base = ROOT / "test"
    module = base / "module-level"
    program = base / "program-level"
    r = Runner()

    if not skip_mypy:
        print("mypy --strict src/")
        sources = [str(ROOT / "src" / s) for s in (PARSE, CHECK, CHECK_PROGRAM)]
        proc = subprocess.run(["mypy", "--strict", *sources], capture_output=True, text=True)
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
        r.module_test(p, module, interpreter)

    print("program-level/well-formed")
    for d in sorted(p for p in (program / "well-formed").iterdir() if p.is_dir()):
        if not (d / EXPECTED_FILE).exists():
            r.bad(f"{d.relative_to(ROOT)} (run)", "missing expected")
    r.run_multi_file_tests(program / "well-formed", interpreter)

    print("program-level/ill-formed")
    r.run_multi_file_tests(program / "ill-formed", interpreter)

    r.summary()


if __name__ == "__main__":
    main()
