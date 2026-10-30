#!/usr/bin/env python3
"""D2 diagram of dependencies between repositories of the organisation, from a directory holding a clone of
each, written to standard output

An edge is a reference in one repository to a release, pages or git URL of another. A reference to a
release asset or to the latest pages names its own version; any other reference needs a comment on the
same or preceding line, "pin: <label>" for a version bumped by hand or "tracks: <label>" for one that
follows the target. Links to repositories, issues and pull requests aren't dependencies. Each repository
with a release shows its latest, and a pin of an earlier release is highlighted."""

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
    version: str | None = None  # Pinned release


def tracked_files(repo: pathlib.Path) -> list[pathlib.Path]:
    names = subprocess.run(
        ["git", "-C", repo, "ls-files", "-z"], capture_output=True, check=True
    ).stdout
    return [repo / name for name in names.decode().split("\0") if name]


def latest_release(repo: str) -> str | None:
    view = subprocess.run(
        [
            "gh",
            "release",
            "view",
            "--repo",
            f"{ORG}/{repo}",
            "--json",
            "tagName",
            "--jq",
            ".tagName",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return view.stdout.strip() if view.returncode == 0 else None


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
        return Edge(
            source, repo, f"release {release['version']}", pinned=True, version=release["version"]
        )
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
    latest = {repo.name: latest_release(repo.name) for repo in repos}

    def node(repo: pathlib.Path) -> str:
        label = f"{repo.name}\\n{latest[repo.name]}" if latest[repo.name] else repo.name
        return f'"{repo.name}": "{label}"\n'

    def link(e: Edge) -> str:
        behind = e.version is not None and e.version != latest[e.target]
        label = f"{e.label}, latest {latest[e.target]}" if behind else e.label
        style = "behind" if behind else "pinned" if e.pinned else "tracking"
        return f'"{e.source}" -> "{e.target}": {label} {{class: {style}}}\n'

    nodes = "".join(map(node, repos))
    links = "".join(
        link(e) for repo in repos for e in sorted(edges(repo), key=lambda e: (e.target, e.label))
    )
    return f"""vars: {{
  d2-config: {{ layout-engine: elk }}
  d2-legend: Key {{
    x -> y: Pin, moved by hand {{ class: pinned }}
    x -> y: Follows target {{ class: tracking }}
    x -> y: Pin behind latest release {{ class: behind }}
    x.style.opacity: 0
    y.style.opacity: 0
  }}
}}
direction: right
classes: {{
  pinned: {{ style.stroke: "#333333" }}
  tracking: {{ style.stroke: "#333333"; style.stroke-dash: 4 }}
  behind: {{ style.stroke: "#b00020" }}
}}
{nodes}{links}"""


def main() -> None:
    (root,) = map(pathlib.Path, sys.argv[1:])
    repos = sorted(path for path in root.iterdir() if (path / ".git").exists())
    sys.stdout.write(d2(repos))


if __name__ == "__main__":
    main()
