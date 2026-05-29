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


# ill-formed/semantic tests that purepy_check.py currently rejects (exit 3).
SEMANTIC_CAUGHT = {
    "duplicate_def_in_region",
    "unreachable",
    "self_capture",
    "self_capture_lambda",
    "shadow_captured",
    "shadow_captured_global",
    "shadow_captured_mutual",
    "cond_partial_def",
    "mutual_split_by_assign",
    "mutual_split_by_call_late_binding",
    "mutual_split_by_call_nameerror",
    "mutual_def_block_local",
    "no_else",
    "unbound_local",
    "import_in_def",
    "import_in_if",
    "import_in_match_case",
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


def parse_cmd(path):
    return ["python3", str(ROOT / "src" / "purepy_parse.py"), str(path)]


def check_cmd(path):
    return ["python3", str(ROOT / "src" / "purepy_check.py"), str(path)]


def run_python(label, interpreter, path, cwd=None, expected_path=None):
    """Run a script under Python; compare output to .expected, or check stderr
    for the class named in .exception.expected. cwd defaults to current; if set,
    path is passed as its filename (relative to cwd)."""
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
            bad(label, f"expected {expected}, got: {proc.stderr.strip()[:200]}")
        else:
            ok(label)
        return

    if proc.returncode != 0:
        bad(label, f"exit {proc.returncode}: {proc.stderr.strip()[:200]}")
        return
    expected = expected_path.read_text() if expected_path.exists() else ""
    if proc.stdout != expected:
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
        sources = [str(ROOT / "src" / "purepy_parse.py"), str(ROOT / "src" / "purepy_check.py")]
        proc = subprocess.run(["mypy", "--strict", *sources], capture_output=True, text=True)
        if proc.returncode == 0:
            ok("src/")
        else:
            bad("src/", proc.stdout.strip()[:400])

    print("well-formed")
    files = sorted(wf.glob("*.py"))
    for sub in ("conditionals", "functions", "scopes"):
        files += sorted((wf / sub).glob("*.py"))
    for p in files:
        rel = p.relative_to(ROOT)
        expect_exit(f"{rel} (parse)", parse_cmd(p), 0)
        expect_exit(f"{rel} (check)", check_cmd(p), 0)
        run_python(f"{rel} (run)", interpreter, p)

    print("well-formed/multi-file")
    mf_root = wf / "multi-file"
    mf_dirs = sorted(p for p in mf_root.iterdir() if p.is_dir()) if mf_root.exists() else []
    for d in mf_dirs:
        rel = d.relative_to(ROOT)
        main_py = d / "main.py"
        if main_py.exists():
            run_python(f"{rel} (run)", interpreter, main_py, cwd=d, expected_path=d / "expected")
        else:
            bad(str(rel), "missing main.py")

    print("well-formed/pending")
    for p in sorted((wf / "pending").glob("*.py")):
        expect_exit(str(p.relative_to(ROOT)), parse_cmd(p), 2)

    print("ill-formed/semantic")
    for p in sorted((base / "ill-formed" / "semantic").glob("*.py")):
        rel = p.relative_to(ROOT)
        expect_exit(f"{rel} (parse)", parse_cmd(p), 0)
        if p.stem in SEMANTIC_CAUGHT:
            expect_exit(f"{rel} (check)", check_cmd(p), 3)
        run_python(f"{rel} (run)", interpreter, p)

    print("ill-formed/unsupported")
    for p in sorted((base / "ill-formed" / "unsupported").glob("*.py")):
        expect_exit(str(p.relative_to(ROOT)), parse_cmd(p), 1)

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
