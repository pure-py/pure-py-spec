#!/usr/bin/env python3
"""Print isabelle-purepy worktree for current issue, if any"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys


def git(*args: str, cwd: pathlib.Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def worktrees(clone: pathlib.Path) -> list[tuple[pathlib.Path, str]]:
    """Path and branch of each worktree of clone, with an empty branch for a detached worktree"""
    entries = [
        dict(line.split(" ", 1) for line in entry.splitlines() if " " in line)
        for entry in git("worktree", "list", "--porcelain", cwd=clone).split("\n\n")
    ]
    return [
        (pathlib.Path(entry["worktree"]), entry.get("branch", "").removeprefix("refs/heads/"))
        for entry in entries
    ]


def main() -> None:
    spec = pathlib.Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    clone = spec.parent / "isabelle-purepy"
    issue = re.match(r"\d+-", git("branch", "--show-current"))
    if not issue or not (clone / ".git").is_dir():
        return
    matching = [path for path, branch in worktrees(clone) if branch.startswith(issue[0])]
    if len(matching) > 1:
        sys.exit(
            f"several worktrees of {clone} on branches of issue {issue[0][:-1]}: {', '.join(map(str, matching))}"
        )
    if matching:
        print(matching[0])


if __name__ == "__main__":
    main()
