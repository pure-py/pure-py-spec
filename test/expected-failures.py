#!/usr/bin/env python3
"""Run suite against type checker, and fail unless failing tests are exactly listed expected failures"""

from __future__ import annotations

import argparse
import pathlib
import sys

from purepy_conformance import check_conformance

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED = ROOT / "test" / "expected-failures.txt"


def expected_failures() -> list[str]:
    """Listed tests, without the issue each waits on"""
    return [line.split("\t")[0] for line in EXPECTED.read_text().splitlines()]


def covers(entry: str, test: str) -> bool:
    return entry == test or (entry.endswith("/") and test.startswith(entry))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-expected-failures", action="store_true")
    args, conformance_args = parser.parse_known_args()
    failed = check_conformance(["--no-run", "--check-messages", *conformance_args]).failed
    listed = [] if args.no_expected_failures else expected_failures()
    unexpected = [test for test in failed if not any(covers(entry, test) for entry in listed)]
    stale = [entry for entry in listed if not any(covers(entry, test) for test in failed)]
    print(f"report: {len(failed)} failures, {len(listed)} expected failures listed")
    for test in unexpected:
        print(f"report: unexpected failure {test}")
    for entry in stale:
        print(f"report: no failure under listed {entry}")
    sys.exit(1 if len(unexpected) + len(stale) > 0 else 0)


if __name__ == "__main__":
    main()
