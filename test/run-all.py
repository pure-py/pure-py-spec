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


# ill-formed/semantic tests the checker does NOT yet reject; everything else
# must exit 3. Add a stem here to stage a test for a not-yet-implemented check.
SEMANTIC_PENDING = {
    "currying",
    "match_int_pat_on_list",
    "match_list_pat_on_tuple",
    "match_str_pat_on_int",
    "match_tuple_pat_on_int",
    "match_tuple_pat_on_list",
}


passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {label}")


def bad(label, msg):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {label} ({msg})")


def expect_exit(label, cmd, expected):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == expected:
        ok(label)
    else:
        bad(label, f"expected exit {expected}, got {proc.returncode}")


def script_cmd(script, path):
    return ["python3", str(ROOT / "src" / script), str(path)]


def run_multi_file_tests(category_root, interpreter):
    """Each subdir is a test: main.py, expected_exit, plus optional fixtures and expected file."""
    for d in sorted(p for p in category_root.iterdir() if p.is_dir()):
        rel = d.relative_to(ROOT)
        main_py = d / "main.py"
        expected_exit_code = int((d / "expected_exit").read_text().strip())
        expect_exit(f"{rel} (check)", script_cmd("purepy_check_program.py", main_py), expected_exit_code)
        expected_path = d / "expected"
        if expected_path.exists():
            run_python(f"{rel} (run)", interpreter, main_py, cwd=d, expected_path=expected_path)


def run_python(label, interpreter, path, cwd=None, expected_path=None):
    """Run a script under Python; compare stdout to expected_path, or check
    stderr for the class named in .exception.expected sibling."""
    if expected_path is None:
        expected_path = path.with_suffix(".expected")
    exception_path = path.with_suffix(".exception.expected")
    cmd_path = path.name if cwd is not None else str(path)
    proc = subprocess.run([interpreter, cmd_path], cwd=cwd, capture_output=True, text=True)

    if exception_path.exists():
        expected = exception_path.read_text().strip()
        if proc.returncode == 0:
            bad(label, f"expected {expected} but script succeeded")
        elif expected not in proc.stderr:
            bad(label, f"expected {expected}, got: {proc.stderr.strip()}")
        else:
            ok(label)
        return

    if proc.returncode != 0:
        bad(label, f"exit {proc.returncode}: {proc.stderr.strip()}")
        return
    if proc.stdout != expected_path.read_text():
        bad(label, "output mismatch")
    else:
        ok(label)


def main():
    skip_mypy = "--no-mypy" in sys.argv
    if skip_mypy:
        sys.argv.remove("--no-mypy")
    interpreter = sys.argv[1] if len(sys.argv) > 1 else "python3"
    base = ROOT / "test"
    wf = base / "well-formed"

    if not skip_mypy:
        print("mypy --strict src/")
        sources = [
            str(ROOT / "src" / "purepy_parse.py"),
            str(ROOT / "src" / "purepy_check.py"),
            str(ROOT / "src" / "purepy_check_program.py"),
        ]
        proc = subprocess.run(["mypy", "--strict", *sources], capture_output=True, text=True)
        if proc.returncode == 0:
            ok("src/")
        else:
            bad("src/", proc.stdout.strip()[:400])

    print("well-formed")
    files = sorted(
        p for p in wf.rglob("*.py")
        if "multi-file" not in p.parts and "pending" not in p.parts
    )
    for p in files:
        rel = p.relative_to(ROOT)
        if not p.with_suffix(".expected").exists():
            bad(f"{rel} (run)", "missing .expected")
            continue
        expect_exit(f"{rel} (parse)", script_cmd("purepy_parse.py", p), 0)
        expect_exit(f"{rel} (check)", script_cmd("purepy_check.py", p), 0)
        run_python(f"{rel} (run)", interpreter, p)

    print("well-formed/multi-file")
    for d in sorted(p for p in (wf / "multi-file").iterdir() if p.is_dir()):
        if not (d / "expected").exists():
            bad(f"{d.relative_to(ROOT)} (run)", "missing expected")
    run_multi_file_tests(wf / "multi-file", interpreter)

    print("well-formed/pending")
    for p in sorted((wf / "pending").glob("*.py")):
        expect_exit(str(p.relative_to(ROOT)), script_cmd("purepy_parse.py", p), 2)

    print("ill-formed/semantic")
    for p in sorted((base / "ill-formed" / "semantic").glob("*.py")):
        rel = p.relative_to(ROOT)
        expect_exit(f"{rel} (parse)", script_cmd("purepy_parse.py", p), 0)
        if p.stem not in SEMANTIC_PENDING:
            expect_exit(f"{rel} (check)", script_cmd("purepy_check.py", p), 3)
        run_python(f"{rel} (run)", interpreter, p)

    print("ill-formed/multi-file")
    run_multi_file_tests(base / "ill-formed" / "multi-file", interpreter)

    print("ill-formed/unsupported")
    for p in sorted((base / "ill-formed" / "unsupported").glob("*.py")):
        expect_exit(str(p.relative_to(ROOT)), script_cmd("purepy_parse.py", p), 1)

    print("syntactic-only")
    for p in sorted((base / "syntactic-only").glob("*.py")):
        if not p.name.startswith("_"):
            expect_exit(str(p.relative_to(ROOT)), [interpreter, str(p)], 0)

    total = passed + failed
    print()
    if failed:
        print(f"{RED}✗ {passed}/{total} passed, {failed} failed{RESET}")
        sys.exit(1)
    print(f"{GREEN}✓ {total}/{total} passed{RESET}")


if __name__ == "__main__":
    main()
