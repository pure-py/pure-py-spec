#!/usr/bin/env python3
"""D2 diagram of dependencies between repositories of the organisation, from a directory holding a clone of
each, written to standard output

An edge is a reference in one repository to a release, pages or git URL of another. A reference to a
release asset or to the latest pages names its own version; any other reference needs a comment on the
same or preceding line, "pin: <label>" for a version bumped by hand or "tracks: <label>" for one that
follows the target. Links to repositories, issues and pull requests aren't dependencies."""

import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

ORG = "pure-py"
PAGES = f"{ORG}.github.io"
URL = re.compile(
    rf"https://(?:github\.com/{ORG}/(?P<repo>[\w.-]+)|{re.escape(PAGES)})(?P<path>[\w./$@{{}}-]*)"
)
RELEASE = re.compile(r"^/(?:releases/download/)?(?P<version>v\d[\d.]*)/")
LATEST = re.compile(r"^/latest/")
ANNOTATION = re.compile(r"\b(?P<kind>pin|tracks): (?P<label>[^#]*?)\s*$")


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str
    pinned: bool


def tracked_files(repo: pathlib.Path) -> list[pathlib.Path]:
    names = subprocess.run(
        ["git", "-C", repo, "ls-files", "-z"], capture_output=True, check=True
    ).stdout
    return [repo / name for name in names.decode().split("\0") if name]


def edge(source: str, lines: list[str], index: int, match: re.Match[str]) -> Edge | None:
    """Dependency at a URL match on a line, with the preceding line available for an annotation"""
    repo = match["repo"]
    path = match["path"]
    if repo is None:
        repo, _, rest = path.lstrip("/").partition("/")
        path = "/" + rest
        if repo == "":
            repo = PAGES
    git = repo.endswith(".git")
    repo = repo.removesuffix(".git")
    if repo == source or path.startswith(("/issues/", "/pull/")):
        return None
    if release := RELEASE.match(path):
        return Edge(source, repo, f"release {release['version']}", pinned=True)
    if LATEST.match(path):
        return Edge(source, repo, "latest release", pinned=False)
    annotated = [ANNOTATION.search(line) for line in lines[max(index - 1, 0) : index + 1]]
    if annotation := next((a for a in reversed(annotated) if a), None):
        return Edge(source, repo, annotation["label"], pinned=annotation["kind"] == "pin")
    if git:
        sys.exit(
            f"{source}: unannotated reference to {repo} at line {index + 1}: {lines[index].strip()}"
        )
    return None


def edges(repo: pathlib.Path) -> set[Edge]:
    def edges_of(path: pathlib.Path) -> set[Edge]:
        try:
            lines = path.read_text().splitlines()
        except (UnicodeDecodeError, OSError):
            return set()
        found = (
            edge(repo.name, lines, i, match)
            for i, line in enumerate(lines)
            for match in URL.finditer(line)
        )
        return {e for e in found if e}

    return set().union(*map(edges_of, tracked_files(repo)))


def d2(repos: list[pathlib.Path]) -> str:
    def style(e: Edge) -> str:
        return "pinned" if e.pinned else "tracking"

    nodes = "".join(f'"{repo.name}"\n' for repo in repos)
    links = "".join(
        f'"{e.source}" -> "{e.target}": {e.label} {{class: {style(e)}}}\n'
        for repo in repos
        for e in sorted(edges(repo), key=lambda e: (e.target, e.label))
    )
    return f"""vars: {{ d2-config: {{ layout-engine: elk }} }}
direction: right
classes: {{
  pinned: {{ style.stroke: "#333333" }}
  tracking: {{ style.stroke: "#333333"; style.stroke-dash: 4 }}
}}
{nodes}{links}"""


def main() -> None:
    (root,) = map(pathlib.Path, sys.argv[1:])
    repos = sorted(path for path in root.iterdir() if (path / ".git").exists())
    sys.stdout.write(d2(repos))


if __name__ == "__main__":
    main()
