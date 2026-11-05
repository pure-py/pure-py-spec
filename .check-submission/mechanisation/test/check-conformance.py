#!/usr/bin/env python3
import argparse
import pathlib
import sys

import ourlang_conformance
from ourlang_conformance import Results, run

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
SRC = ROOT / "src" / "ourlang"
PYTHON_VERSION = (ROOT / ".python-version").read_text().strip()


def check_lint(r: Results) -> None:
    with r.test("mypy and ruff"):
        sources = sorted(str(path) for path in SRC.glob("*.py")) + [
            str(TEST / "check-conformance.py")
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-lint", action="store_true")
    args, conformance_args = parser.parse_known_args()
    if not args.no_lint:
        lint = Results()
        check_lint(lint)
        lint.summary()
        if lint.failed:
            sys.exit(1)
    ourlang_conformance.main(
        ["--type-checker", f"{sys.executable} -m ourlang --check", *conformance_args]
    )


if __name__ == "__main__":
    main()
