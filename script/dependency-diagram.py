#!/usr/bin/env python3
"""Diagram of dependencies between the organisation's repositories, drawn by D2 as SVG. Each kind of node is a
subclass of Node, recognising a project from its project file, and each kind of edge a subclass of Edge,
finding edges of its kind across the organisation; defining a subclass registers the kind."""

import html
import json
import pathlib
import re
import subprocess
import sys
import textwrap
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import takewhile
from typing import ClassVar

ORG = "pure-py"
PAGES = f"{ORG}.github.io"
URL = re.compile(
    rf"https://(?:github\.com/{ORG}/(?P<repo>[\w.-]+)|{re.escape(PAGES)})(?P<path>[\w./$@{{}}-]*)"
)
RELEASE = re.compile(r"^/(?:releases/download/)?(?P<version>v\d[\d.]*)/")
LATEST = re.compile(r"^/latest/")
ANNOTATION = re.compile(r"\b(?P<kind>pin|tracks): (?P<label>[^#]*?)\s*$")
WHEEL = re.compile(r"/(?P<package>[A-Za-z0-9_.]+?)-\d[^/]*\.whl$")
ROOT_TOKEN = re.compile(r'"(?P<quoted>[^"]*)"|(?P<bare>[^\s"]+)')
ROOT_KEYWORDS = {"session", "in", "=", "+", "description", "options", "sessions", "directories"}
ROOT_KEYWORDS |= {
    "theories",
    "document_theories",
    "document_files",
    "export_files",
    "export_classpath",
}
MAKE_VARIABLE = re.compile(r"^(?P<name>[A-Za-z_]\w*)\s*[:?]?=\s*(?P<value>.*)$", re.MULTILINE)
MAKE_REFERENCE = re.compile(r"\$[({](?P<name>\w+)[)}]")
ISABELLE_BUILD = re.compile(r"\bisabelle\s+build\b")
ICONS = pathlib.Path(__file__).resolve().parent / "icons"
D2 = ["d2", "--pad", "16", "--elk-nodeNodeBetweenLayers", "30", "--elk-edgeNodeBetweenLayers", "15"]
D2 += ["--elk-padding", "[top=40,left=20,bottom=20,right=20]"]
WRAP = 26  # Characters per line of a description


def required(description: str | None, path: pathlib.PurePath) -> str:
    assert description, f"{path}: project has no description"
    return description


@dataclass(frozen=True)
class Node:
    """Project recognised from its project file"""

    kinds: ClassVar[list[type["Node"]]] = []
    file: ClassVar[str]
    icon: ClassVar[str]
    name: str
    description: str
    directory: pathlib.PurePath

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        Node.kinds.append(cls)

    @classmethod
    def recognise(cls, repo: pathlib.Path, path: pathlib.PurePath) -> "Node | None":
        raise NotImplementedError

    def lines(self) -> list[str]:
        return textwrap.wrap(self.description, WRAP)


class PythonProject(Node):
    """Python project with a build system or below the repository root, since a Python project file at the
    root without one only serves the tests of another kind of project"""

    file = "pyproject.toml"
    icon = "python.svg"

    @classmethod
    def recognise(cls, repo: pathlib.Path, path: pathlib.PurePath) -> Node | None:
        config = tomllib.loads((repo / path).read_text())
        if "build-system" not in config and path.parent == pathlib.PurePath("."):
            return None
        meta = config["project"]
        return cls(meta["name"], required(meta.get("description"), path), path.parent)


@dataclass(frozen=True)
class IsabelleProject(Node):
    """Isabelle sessions of a ROOT file, named after the first"""

    file = "ROOT"
    icon = "isabelle.png"
    sessions: tuple[str, ...]
    imports: tuple[str, ...]  # Parents and listed sessions of the sessions

    @classmethod
    def recognise(cls, repo: pathlib.Path, path: pathlib.PurePath) -> Node | None:
        tokens = [
            m["quoted"] if m["quoted"] is not None else m["bare"]
            for m in ROOT_TOKEN.finditer((repo / path).read_text())
        ]
        after = {i: tokens[i + 1] for i in range(len(tokens) - 1)}
        sessions = tuple(after[i] for i, t in enumerate(tokens) if t == "session" and i in after)
        if not sessions:
            return None
        second = next((i for i, t in enumerate(tokens) if t == "session" and i > 0), len(tokens))
        description = next(
            (after[i] for i, t in enumerate(tokens[:second]) if t == "description"), None
        )
        listed = tuple(
            entry
            for i, t in enumerate(tokens)
            if t == "sessions"
            for entry in takewhile(lambda u: u not in ROOT_KEYWORDS, tokens[i + 1 :])
        )
        parents = tuple(
            after[i] for i, t in enumerate(tokens) if t == "=" and after.get(i + 1) == "+"
        )
        return cls(
            sessions[0], required(description, path), path.parent, sessions, parents + listed
        )


class SvelteKitProject(Node):
    file = "svelte.config.js"
    icon = "svelte.svg"

    @classmethod
    def recognise(cls, repo: pathlib.Path, path: pathlib.PurePath) -> Node | None:
        package = json.loads((repo / path.parent / "package.json").read_text())
        return cls(package["name"], required(package.get("description"), path), path.parent)


def tracked_files(repo: pathlib.Path) -> list[pathlib.Path]:
    names = subprocess.run(
        ["git", "-C", repo, "ls-files", "-z"], capture_output=True, check=True
    ).stdout
    return [repo / name for name in names.decode().split("\0") if name]


def nodes(repo: pathlib.Path) -> list[Node]:
    kinds = {kind.file: kind for kind in Node.kinds}
    found = (
        kinds[path.name].recognise(repo, path.relative_to(repo))
        for path in tracked_files(repo)
        if path.name in kinds
    )
    return [n for n in found if n]


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


@dataclass(frozen=True)
class Organisation:
    repos: list[pathlib.Path]
    nodes: dict[str, list[Node]]
    latest: dict[str, str | None]

    def node_id(self, repo: str, node: Node | None = None) -> str:
        """Repository, or node within a repository holding several"""
        return (
            f'"{repo}"."{node.name}"' if node and len(self.nodes.get(repo, [])) > 1 else f'"{repo}"'
        )

    def owner(self, repo: str, path: pathlib.PurePath) -> Node | None:
        """Node of a file: the one in the deepest directory containing it, where a node at the repository
        root owns only its own project file"""
        owners = [
            n
            for n in self.nodes[repo]
            if path == n.directory / n.file
            or (n.directory != pathlib.PurePath(".") and n.directory in path.parents)
        ]
        return max(owners, key=lambda n: len(n.directory.parts), default=None)


@dataclass(frozen=True)
class Edge:
    """Dependency of the source node on the target"""

    kinds: ClassVar[list[type["Edge"]]] = []
    key: ClassVar[str]
    stroke: ClassVar[str] = "#333333"
    dash: ClassVar[int] = 0
    source: str
    target: str
    label: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        Edge.kinds.append(cls)

    @classmethod
    def find(cls, org: Organisation) -> Iterator["Edge"]:
        return iter(())


def dependency_kind(pyproject: pathlib.Path, url: str) -> str:
    """Runtime or dev dependency, for Python package taken from a release asset"""
    project = tomllib.loads(pyproject.read_text()).get("project", {})
    runtime = any(url in dep for dep in project.get("dependencies", []))
    return "runtime dependency" if runtime else "dev dependency"


def reference(
    org: Organisation,
    source_repo: str,
    path: pathlib.Path,
    lines: list[str],
    index: int,
    match: re.Match[str],
) -> tuple[bool, str, str, str, str | None] | None:
    """Pin or tracking dependency implied by a URL in a file, as whether pinned, target, target repository,
    label and pinned release; none if a plain link to a repository, issue or pull request, which is a
    reference rather than a dependency. A "pin:" or "tracks:" comment on the same or preceding line is
    interpreted as a label on the dependency."""
    repo = match["repo"]
    url_path = match["path"]
    if repo is None:
        repo, _, rest = url_path.lstrip("/").partition("/")
        url_path = "/" + rest
        if repo == "":
            repo = PAGES
    git = repo.endswith(".git")
    repo = repo.removesuffix(".git")
    if repo == source_repo or url_path.startswith(("/issues/", "/pull/")):
        return None
    target = org.node_id(repo)
    if release := RELEASE.match(url_path):
        label = release["version"]
        if path.name == "pyproject.toml":
            label = f"{dependency_kind(path, match[0])}, {label}"
        if wheel := WHEEL.search(url_path):
            package = re.sub(r"[-_.]+", "-", wheel["package"]).lower()
            built = (
                n
                for n in org.nodes.get(repo, [])
                if re.sub(r"[-_.]+", "-", n.name).lower() == package
            )
            target = org.node_id(repo, next(built, None))
        return True, target, repo, label, release["version"]
    if LATEST.match(url_path):
        return False, target, repo, "latest release", None
    annotated = [ANNOTATION.search(line) for line in lines[max(index - 1, 0) : index + 1]]
    if annotation := next((a for a in reversed(annotated) if a), None):
        return annotation["kind"] == "pin", target, repo, annotation["label"], None
    if git:
        sys.exit(
            f"{source_repo}: unannotated reference to {repo} at line {index + 1}: {lines[index].strip()}"
        )
    return None


def references(org: Organisation, pinned: bool) -> Iterator[tuple[str, str, str, str, str | None]]:
    """Source, target, target repository, label and pinned release of each pin, or each tracking
    dependency, in the files of the organisation"""
    for repo in org.repos:
        for path in tracked_files(repo):
            if path.name == "uv.lock":  # Repeats the project file's pins
                continue
            try:
                lines = path.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            source = org.node_id(repo.name, org.owner(repo.name, path.relative_to(repo)))
            for i, line in enumerate(lines):
                for match in URL.finditer(line):
                    found = reference(org, repo.name, path, lines, i, match)
                    if found and found[0] == pinned:
                        yield source, *found[1:]


class Pin(Edge):
    key = "Pin (moved by hand)"

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Edge]:
        for source, target, target_repo, label, version in references(org, pinned=True):
            behind = version is not None and version != org.latest[target_repo]
            yield (PinBehind if behind else Pin)(source, target, label)


class Tracking(Edge):
    key = "Follows target"
    dash = 4

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Edge]:
        for source, target, _, label, _ in references(org, pinned=False):
            yield cls(source, target, label)


class PinBehind(Edge):
    """Found as a pin"""

    key = "Pin behind latest release"
    stroke = "#e00000"


class SessionImport(Edge):
    """Isabelle session building on a session of another repository"""

    key = "Isabelle session import"
    dash = 2

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Edge]:
        projects = [
            (repo.name, n)
            for repo in org.repos
            for n in org.nodes[repo.name]
            if isinstance(n, IsabelleProject)
        ]
        for repo, importer in projects:
            for name in sorted(set(importer.imports) - set(importer.sessions)):
                for other, imported in projects:
                    if other != repo and name in imported.sessions:
                        yield cls(
                            org.node_id(repo, importer),
                            org.node_id(other, imported),
                            "session import",
                        )


def recipes(makefile: str) -> list[list[str]]:
    """Recipe lines of each rule of a Makefile, with variables expanded"""
    text = makefile.replace("\\\n", " ")
    variables = {m["name"]: m["value"].strip() for m in MAKE_VARIABLE.finditer(text)}

    def expand(line: str, depth: int = 5) -> str:
        expanded = MAKE_REFERENCE.sub(lambda m: variables.get(m["name"], m[0]), line)
        return expanded if depth == 0 or expanded == line else expand(expanded, depth - 1)

    rules: list[list[str]] = []
    for line in text.splitlines():
        if line.startswith("\t") and rules:
            rules[-1].append(expand(line.strip()))
        elif re.match(r"^[^\s#=][^=]*:(?!=)", line):
            rules.append([])
    return rules


class GeneratedCode(Edge):
    """Python project with source written by a Makefile recipe after an Isabelle build in the same repository"""

    key = "Code generated from target"
    dash = 2

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Edge]:
        for repo in org.repos:
            makefile = repo / "Makefile"
            built = [n for n in org.nodes[repo.name] if isinstance(n, IsabelleProject)]
            if not makefile.exists() or not built:
                continue
            for recipe in recipes(makefile.read_text()):
                start = next(
                    (i for i, line in enumerate(recipe) if ISABELLE_BUILD.search(line)), None
                )
                if start is None:
                    continue
                written = {word for line in recipe[start + 1 :] for word in line.split()}
                for p in org.nodes[repo.name]:
                    source = (p.directory / "src").as_posix()
                    if isinstance(p, PythonProject) and any(
                        w.startswith(source + "/") for w in written
                    ):
                        yield cls(
                            org.node_id(repo.name, p),
                            org.node_id(repo.name, built[0]),
                            "generated from",
                        )


def d2(org: Organisation) -> str:
    def node(repo: pathlib.Path) -> str:
        """Repository, drawn as its node when it holds one, otherwise containing its nodes"""
        lines = [repo.name]
        own = org.nodes[repo.name]
        if len(own) == 1 and own[0].name != repo.name:
            lines.append(own[0].name)
        version = org.latest[repo.name]
        if len(own) == 1:
            label = "\\n".join(lines + ([version] if version else []) + own[0].lines())
            return (
                f'"{repo.name}": "{label}" {{ class: standalone; icon: {ICONS / own[0].icon} }}\n'
            )
        label = f"{repo.name} {version}" if version else repo.name
        inner = "".join(
            f'  "{n.name}": "{"\\n".join([n.name, *n.lines()])}" {{ class: project; icon: {ICONS / n.icon} }}\n'
            for n in own
        )
        return f'"{repo.name}": "{label}" {{\n  class: repository\n{inner}}}\n'

    found = sorted(
        {e for kind in Edge.kinds for e in kind.find(org)},
        key=lambda e: (e.target, e.source, e.label),
    )
    links = "".join(
        f"{e.source} -> {e.target}: {e.label} {{class: {type(e).__name__}}}\n" for e in found
    )
    styles = "".join(
        f'  {kind.__name__}: {{ style.stroke: "{kind.stroke}"; style.stroke-dash: {kind.dash}; style.font-size: 17 }}\n'
        for kind in Edge.kinds
    )
    return f"""vars: {{ d2-config: {{ layout-engine: elk }} }}
direction: down
classes: {{
{styles}  project: {{ width: 230; style.font-size: 16 }}
  standalone: {{ width: 230; style.font-size: 16 }}
  repository: {{ style.font-size: 20 }}
}}
{"".join(map(node, org.repos))}{links}"""


def italicise(svg: str, lines: set[str]) -> str:
    """Description lines of node labels in the italic font, which D2 can't set within a label"""
    return re.sub(
        r"(<tspan[^>]*)>([^<]*)</tspan>",
        lambda m: (
            f'{m[1]} class="text-italic">{m[2]}</tspan>' if html.unescape(m[2]) in lines else m[0]
        ),
        svg,
    )


def main() -> None:
    root, output = map(pathlib.Path, sys.argv[1:])
    repos = sorted(path for path in root.iterdir() if (path / ".git").exists())
    org = Organisation(
        repos, {r.name: nodes(r) for r in repos}, {r.name: latest_release(r.name) for r in repos}
    )
    lines = {line for found in org.nodes.values() for n in found for line in n.lines()}
    glyphs = "".join(sorted({c for line in lines for c in line if not c.isspace()}))
    # Italic label in white, so the italic font embedded by D2 has every glyph of the descriptions
    source = d2(org) + (
        f'glyphs: "{glyphs}" {{ near: bottom-right; shape: text; style: {{ italic: true; bold: false;'
        " font-size: 8; font-color: \"#FFFFFF\" } }\n"
    )
    drawn = subprocess.run(
        [*D2, "-", "-"], input=source, capture_output=True, text=True, check=False
    )
    if drawn.returncode != 0:
        sys.exit(drawn.stderr)
    output.write_text(italicise(drawn.stdout, lines))


if __name__ == "__main__":
    main()
