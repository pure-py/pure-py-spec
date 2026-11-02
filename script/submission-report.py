#!/usr/bin/env python3
"""Report on a make target, run prerequisite by prerequisite: a tab-separated line per target described by
a double-hash comment on the line above its rule, giving its name, the description, whether it passed, failed or wasn't
run because a prerequisite failed, and the detail its recipe printed on lines starting "report:"; a report
line with a tab separates the label and outcome of a check within the target, giving a line of its own with
no target. Written to standard output, with the make output on standard error. Further arguments are passed
to make. Exits with failure if any target failed. With --check instead of a target, checks that every
target with a recipe is described, except the special and internal ones starting with a dot."""

import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import cache

RULE = re.compile(r"^(?P<target>[^\s:#=$%]+):(?!=)\s*(?P<prerequisites>.*)$")
DESCRIPTION = "## "


@dataclass(frozen=True)
class Rule:
    description: str
    prerequisites: list[str]
    recipe: bool


def rules(makefile: str) -> dict[str, Rule]:
    lines = makefile.replace("\\\n", " ").splitlines()
    result: dict[str, Rule] = {}
    for i, line in enumerate(lines):
        if match := RULE.match(line):
            above = lines[i - 1] if i > 0 else ""
            description = above.removeprefix(DESCRIPTION) if above.startswith(DESCRIPTION) else ""
            prerequisites = [p for p in match["prerequisites"].split() if not p.startswith("$")]
            recipe = i + 1 < len(lines) and lines[i + 1].startswith("\t")
            result[match["target"]] = Rule(description, prerequisites, recipe)
    return result


def main() -> None:
    root, *options = sys.argv[1:]
    graph = rules(pathlib.Path("Makefile").read_text())
    if root == "--check":
        undescribed = [
            t
            for t, rule in graph.items()
            if rule.recipe and not rule.description and not t.startswith(".")
        ]
        for target in undescribed:
            print(f"{target}: no description")
        sys.exit(bool(undescribed))
    report: list[str] = []

    @cache
    def run(target: str) -> str:
        """Outcome of a target, after those of its prerequisites, reported if the target is described"""
        if target not in graph:
            return "passed"
        rule = graph[target]
        assert rule.description or not rule.recipe or target.startswith("."), (
            f"{target} has no description"
        )
        details: list[str] = []
        checks: list[str] = []
        if any(outcome != "passed" for outcome in [run(p) for p in rule.prerequisites]):
            outcome = "not run"
        else:
            made = subprocess.run(
                ["make", target, *options],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "REPORT": "1"},
            )
            sys.stderr.write(made.stdout + made.stderr)
            outcome = "passed" if made.returncode == 0 else "failed"
            lines = [
                line.removeprefix("report: ")
                for line in made.stdout.splitlines()
                if line.startswith("report: ")
            ]
            details = [line for line in lines if "\t" not in line]
            checks = [line for line in lines if "\t" in line]
            if outcome == "failed" and not details:
                output = [
                    line
                    for line in made.stderr.splitlines()
                    if line and not line.startswith("make")
                ]
                details = output[-1:]
        if rule.description:
            report.append(f"{target}\t{rule.description}\t{outcome}\t{'; '.join(details)}")
            report.extend(f"\t{check}\t" for check in checks)
        return outcome

    outcome = run(root)
    sys.stdout.write("".join(line + "\n" for line in report))
    sys.exit(outcome != "passed")


if __name__ == "__main__":
    main()
