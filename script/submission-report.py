#!/usr/bin/env python3
"""Report on a make target, run prerequisite by prerequisite: a tab-separated line per target that has a
comment above its rule, giving its name, the comment, whether it passed, failed or wasn't run because a
prerequisite failed, and the detail its recipe printed on lines starting "report:", written to standard
output, with the make output on standard error. Further arguments are passed to make. Exits with failure if
any target failed."""

import pathlib
import re
import subprocess
import sys
from functools import cache

RULE = re.compile(r"^(?P<target>[^\s:#=$]+):(?!=)\s*(?P<prerequisites>.*)$")


def rules(makefile: str) -> dict[str, tuple[str, list[str]]]:
    """Comment above the rule, if any, and prerequisites of each target with a rule of its own"""
    result: dict[str, tuple[str, list[str]]] = {}
    previous = ""
    for line in makefile.splitlines():
        if match := RULE.match(line):
            comment = previous[1:].strip() if previous.startswith("#") else ""
            prerequisites = [p for p in match["prerequisites"].split() if not p.startswith("$")]
            result[match["target"]] = (comment, prerequisites)
        previous = line
    return result


def main() -> None:
    root, *options = sys.argv[1:]
    graph = rules(pathlib.Path("Makefile").read_text())
    report: list[str] = []

    @cache
    def run(target: str) -> str:
        """Outcome of a target, after those of its prerequisites, reported if the target has a comment"""
        if target not in graph:
            return "passed"
        comment, prerequisites = graph[target]
        details: list[str] = []
        if any(run(p) != "passed" for p in prerequisites):
            outcome = "not run"
        else:
            made = subprocess.run(
                ["make", target, *options], capture_output=True, text=True, check=False
            )
            sys.stderr.write(made.stdout + made.stderr)
            outcome = "passed" if made.returncode == 0 else "failed"
            details = [
                line.removeprefix("report: ")
                for line in made.stdout.splitlines()
                if line.startswith("report: ")
            ]
        if comment:
            report.append(f"{target}\t{comment}\t{outcome}\t{'; '.join(details)}")
        return outcome

    outcome = run(root)
    sys.stdout.write("".join(line + "\n" for line in report))
    sys.exit(outcome != "passed")


if __name__ == "__main__":
    main()
