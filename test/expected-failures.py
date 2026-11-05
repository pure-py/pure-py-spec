#!/usr/bin/env python3
"""Run suite against type checker, and fail unless failing tests are exactly expected failures listed against open issues"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

from purepy_conformance import check_conformance

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED = ROOT / "test" / "expected-failures.txt"
ISSUE = re.compile(r"(?P<repo>[\w.-]+/[\w.-]+)#(?P<number>\d+)")


def expected_failures() -> list[tuple[str, str]]:
    """Listed tests, each with the issue it waits on"""
    return [
        (test, issue)
        for line in EXPECTED.read_text().splitlines()
        for test, issue in [line.split("\t")]
    ]


def covers(entry: str, test: str) -> bool:
    return entry == test or (entry.endswith("/") and test.startswith(entry))


def issue_state(issue: str) -> str:
    cited = ISSUE.fullmatch(issue)
    assert cited is not None, f"issue not of the form OWNER/REPO#N: {issue}"
    view = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            cited["number"],
            "--repo",
            cited["repo"],
            "--json",
            "state",
            "--jq",
            ".state",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return view.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-expected-failures", action="store_true")
    args, conformance_args = parser.parse_known_args()
    failed = check_conformance(["--no-run", "--check-messages", *conformance_args]).failed
    listed = [] if args.no_expected_failures else expected_failures()
    unexpected = [test for test in failed if not any(covers(entry, test) for entry, _ in listed)]
    stale = [entry for entry, _ in listed if not any(covers(entry, test) for test in failed)]
    closed = sorted(
        issue for issue in {issue for _, issue in listed} if issue_state(issue) != "OPEN"
    )
    print(f"report: {len(failed)} failures, {len(listed)} expected failures listed")
    for test in unexpected:
        print(f"report: unexpected failure {test}")
    for entry in stale:
        print(f"report: no failure under listed {entry}")
    for issue in closed:
        print(f"report: listed issue {issue} closed")
    sys.exit(1 if unexpected or stale or closed else 0)


if __name__ == "__main__":
    main()
