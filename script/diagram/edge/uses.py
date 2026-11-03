from __future__ import annotations

import pathlib
import re
import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass

from diagram.edge import RED, Edge, Style
from diagram.node import Node
from diagram.node.repository import ORG
from diagram.organisation import Organisation

PAGES = f"{ORG}.github.io"
URL = re.compile(
    rf"https://(?:github\.com/{ORG}/(?P<repo>[\w.-]+)|{re.escape(PAGES)})(?P<path>[\w./$@{{}}-]*)"
)
RELEASE = re.compile(r"^/(?:releases/download/)?(?P<version>v\d[\d.]*)/")
LATEST = re.compile(r"^/latest/")
ANNOTATION = re.compile(r"\b(?P<kind>pin|tracks): (?P<label>[^#]*?)\s*$")
WHEEL = re.compile(r"/(?P<package>[A-Za-z0-9_.]+?)-\d[^/]*\.whl$")


def package(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def dependency_kind(pyproject: pathlib.Path, url: str) -> str:
    project = tomllib.loads(pyproject.read_text()).get("project", {})
    runtime = any(url in dep for dep in project.get("dependencies", []))
    return "runtime dependency" if runtime else "dev dependency"


def reference(
    org: Organisation,
    source: Node,
    path: pathlib.Path,
    lines: list[str],
    index: int,
    match: re.Match[str],
) -> Uses | None:
    """Dependency implied by a URL in a file; none if a plain link to a repository, issue or pull request.
    A "pin:" or "tracks:" comment on the same or preceding line is interpreted as a label on the dependency."""
    name = match["repo"]
    url_path = match["path"]
    if name is None:
        name, _, rest = url_path.lstrip("/").partition("/")
        url_path = "/" + rest
        if name == "":
            name = PAGES
    git = name.endswith(".git")
    name = name.removesuffix(".git")
    repo = org.repository(name)
    if repo is None or name == source.repo or url_path.startswith(("/issues/", "/pull/")):
        return None
    if release := RELEASE.match(url_path):
        label = release["version"]
        if path.name == "pyproject.toml":
            label = f"{dependency_kind(path, match[0])}, {label}"
        wheel = WHEEL.search(url_path)
        built = (
            p for p in org.projects[name] if wheel and package(p.name) == package(wheel["package"])
        )
        return Uses(
            source, next(built, repo), label, True, repo.version not in (None, release["version"])
        )
    if LATEST.match(url_path):
        return Uses(source, repo, "latest release", False)
    annotated = [ANNOTATION.search(line) for line in lines[max(index - 1, 0) : index + 1]]
    if annotation := next((a for a in reversed(annotated) if a), None):
        return Uses(source, repo, annotation["label"], annotation["kind"] == "pin")
    if git:
        sys.exit(
            f"{source.repo}: unannotated reference to {name} at line {index + 1}: {lines[index].strip()}"
        )
    return None


def uses(org: Organisation) -> list[Uses]:
    found: list[Uses] = []
    for repo in org.repositories:
        for path in repo.files():
            if path.name == "uv.lock":  # Repeats the project file's pins
                continue
            try:
                lines = path.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            source = org.owner(repo, path.relative_to(repo.path))
            found += [
                r
                for i, line in enumerate(lines)
                for match in URL.finditer(line)
                if (r := reference(org, source, path, lines, i, match))
            ]
    return found


@dataclass(frozen=True)
class Uses(Edge[Node, Node]):
    """Reference by URL to a pinned or latest release of another repository"""

    styles = (
        Style("Pin (moved by hand)"),
        Style("Follows target", dash=4),
        Style("Pin behind latest release", RED),
    )
    pinned: bool
    outdated: bool = False

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Edge[Node, Node]]:
        return iter(uses(org))

    def style(self) -> Style:
        return (
            self.styles[2] if self.outdated else self.styles[0] if self.pinned else self.styles[1]
        )
