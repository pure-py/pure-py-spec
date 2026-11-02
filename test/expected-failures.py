#!/usr/bin/env python3
"""Run the conformance suite against a type checker, with diagnostics checked, and compare the failures with
test/expected-failures.txt, which lists the tests the type checker is expected to fail: one per line, named as
the suite names it, followed by a tab and the issue the test waits on. A directory ending in a slash stands for
every test under it. Fail unless the failures are exactly those listed."""

import argparse
import pathlib
import shlex
import sys

from purepy_conformance import Runner, suite

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED = ROOT / "test" / "expected-failures.txt"


def expected_failures() -> list[tuple[str, str]]:
    """Listed tests, each with the issue it waits on"""
    return [
        (test, issue)
        for line in EXPECTED.read_text().splitlines()
        for test, issue in [line.split("\t")]
    ]


def covers(entry: str, test: str) -> bool:
    return entry == test or (entry.endswith("/") and test.startswith(entry))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type-checker", default="purepy --check")
    parser.add_argument("--jobs", type=int)
    args = parser.parse_args()
    runner = Runner(shlex.split(args.type_checker), None, False, True)
    with suite() as path:
        runner.run_suite(path, args.jobs)
    runner.summary()
    failed = [failure.split(" (", 1)[0] for failure in runner.failed]
    listed = expected_failures()
    unexpected = [test for test in failed if not any(covers(entry, test) for entry, _ in listed)]
    stale = [entry for entry, _ in listed if not any(covers(entry, test) for test in failed)]
    print(f"report: {len(failed)} failures, {len(listed)} expected failures listed")
    for test in unexpected:
        print(f"report: unexpected failure {test}")
    for entry in stale:
        print(f"report: no failure under listed {entry}")
    sys.exit(1 if unexpected or stale else 0)


if __name__ == "__main__":
    main()
