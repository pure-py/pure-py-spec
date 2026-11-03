#!/usr/bin/env python3
"""Diagram of dependencies between the organisation's repositories, drawn by D2 as SVG"""

import html
import json
import pathlib
import re
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass

ORG = "pure-py"
PAGES = f"{ORG}.github.io"
URL = re.compile(
    rf"https://(?:github\.com/{ORG}/(?P<repo>[\w.-]+)|{re.escape(PAGES)})(?P<path>[\w./$@{{}}-]*)"
)
RELEASE = re.compile(r"^/(?:releases/download/)?(?P<version>v\d[\d.]*)/")
LATEST = re.compile(r"^/latest/")
ANNOTATION = re.compile(r"\b(?P<kind>pin|tracks): (?P<label>[^#]*?)\s*$")
WHEEL = re.compile(r"/(?P<package>[A-Za-z0-9_.]+?)-\d[^/]*\.whl$")
SESSION = re.compile(r'^session\s+"?(?P<name>[\w.-]+)"?', re.MULTILINE)
DESCRIPTION = re.compile(r'^\s*description\s+"(?P<text>[^"]*)"', re.MULTILINE)
D2 = ["d2", "--pad", "16", "--elk-nodeNodeBetweenLayers", "30", "--elk-edgeNodeBetweenLayers", "15"]
D2 += ["--elk-padding", "[top=40,left=20,bottom=20,right=20]"]
WRAP = 26  # Characters per line of a description
ICONS = {
    kind: pathlib.Path(__file__).resolve().parent / "icons" / file
    for kind, file in [
        ("Isabelle", "isabelle.png"),
        ("Python", "python.svg"),
        ("SvelteKit", "svelte.svg"),
    ]
}


@dataclass(frozen=True)
class Project:
    kind: str
    name: str
    description: str
    directory: pathlib.PurePath
    file: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    target_repo: str
    label: str
    pinned: bool
    version: str | None = None  # Pinned release


def package(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def project(repo: pathlib.Path, path: pathlib.PurePath) -> Project | None:
    """Project defined by a SvelteKit configuration, Isabelle ROOT file, or Python project file with a build
    system or below the repository root, since a Python project file at the root without one only serves
    the tests of another kind of project"""
    if path.name not in ("svelte.config.js", "ROOT", "pyproject.toml"):
        return None
    text = (repo / path).read_text()
    if path.name == "svelte.config.js":
        package = json.loads((repo / path.parent / "package.json").read_text())
        return described("SvelteKit", package["name"], package.get("description"), path)
    if path.name == "ROOT" and (session := SESSION.search(text)):
        entry = SESSION.split(text[session.end() :], maxsplit=1)[0]
        description = DESCRIPTION.search(entry)
        return described("Isabelle", session["name"], description and description["text"], path)
    if path.name == "pyproject.toml":
        config = tomllib.loads(text)
        if "build-system" in config or path.parent != pathlib.PurePath("."):
            meta = config["project"]
            return described("Python", meta["name"], meta.get("description"), path)
    return None


def described(kind: str, name: str, description: str | None, path: pathlib.PurePath) -> Project:
    assert description, f"{path}: {kind} project {name} has no description"
    return Project(kind, name, description, path.parent, path.name)


def projects(repo: pathlib.Path) -> list[Project]:
    found = (project(repo, path.relative_to(repo)) for path in tracked_files(repo))
    return [p for p in found if p]


def owner(found: list[Project], path: pathlib.PurePath) -> Project | None:
    """Project of a file: the one in the deepest directory containing it, where a project at the repository
    root owns only its own project file"""
    owners = [
        p
        for p in found
        if path == p.directory / p.file
        or (p.directory != pathlib.PurePath(".") and p.directory in path.parents)
    ]
    return max(owners, key=lambda p: len(p.directory.parts), default=None)


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


def dependency_kind(pyproject: pathlib.Path, url: str) -> str:
    """Runtime or dev dependency, for a Python package taken from a release asset"""
    project = tomllib.loads(pyproject.read_text()).get("project", {})
    runtime = any(url in dep for dep in project.get("dependencies", []))
    return "runtime dependency" if runtime else "dev dependency"


def edge(
    found: dict[str, list[Project]],
    source_repo: str,
    source: str,
    path: pathlib.Path,
    lines: list[str],
    index: int,
    match: re.Match[str],
) -> Edge | None:
    """Dependency implied by a URL in a file; none if a plain link to a repository, issue or pull request,
    which is a reference rather than a dependency. A "pin:" or "tracks:" comment on the same or preceding
    line is interpreted as a label on the dependency."""
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
    target = node_id(found, repo)
    if release := RELEASE.match(url_path):
        label = release["version"]
        if path.name == "pyproject.toml":
            label = f"{dependency_kind(path, match[0])}, {label}"
        if wheel := WHEEL.search(url_path):
            target = node_id(
                found,
                repo,
                next(
                    (
                        p
                        for p in found.get(repo, [])
                        if package(p.name) == package(wheel["package"])
                    ),
                    None,
                ),
            )
        return Edge(source, target, repo, label, pinned=True, version=release["version"])
    if LATEST.match(url_path):
        return Edge(source, target, repo, "latest release", pinned=False)
    annotated = [ANNOTATION.search(line) for line in lines[max(index - 1, 0) : index + 1]]
    if annotation := next((a for a in reversed(annotated) if a), None):
        return Edge(source, target, repo, annotation["label"], pinned=annotation["kind"] == "pin")
    if git:
        sys.exit(
            f"{source_repo}: unannotated reference to {repo} at line {index + 1}: {lines[index].strip()}"
        )
    return None


def node_id(found: dict[str, list[Project]], repo: str, p: Project | None = None) -> str:
    """Repository, or project within a repository holding several"""
    return f'"{repo}"."{p.name}"' if p and len(found.get(repo, [])) > 1 else f'"{repo}"'


def edges(found: dict[str, list[Project]], repo: pathlib.Path) -> set[Edge]:
    def edges_of(path: pathlib.Path) -> set[Edge]:
        if path.name == "uv.lock":  # Repeats the project file's pins
            return set()
        try:
            lines = path.read_text().splitlines()
        except (UnicodeDecodeError, OSError):
            return set()
        source = node_id(found, repo.name, owner(found[repo.name], path.relative_to(repo)))
        es = (
            edge(found, repo.name, source, path, lines, i, match)
            for i, line in enumerate(lines)
            for match in URL.finditer(line)
        )
        return {e for e in es if e}

    return set().union(*map(edges_of, tracked_files(repo)))


def d2(repos: list[pathlib.Path]) -> str:
    latest = {repo.name: latest_release(repo.name) for repo in repos}
    found = {repo.name: projects(repo) for repo in repos}

    def node(repo: pathlib.Path) -> str:
        """Repository, drawn as its project when it holds one, otherwise containing its projects"""
        lines = [repo.name]
        own = found[repo.name]
        if len(own) == 1 and own[0].name != repo.name:
            lines.append(own[0].name)
        version = latest[repo.name]
        if len(own) == 1:
            label = "\\n".join(lines + ([version] if version else []) + wrapped(own[0]))
            return f'"{repo.name}": "{label}" {{ class: standalone; icon: {ICONS[own[0].kind]} }}\n'
        label = f"{repo.name} {version}" if version else repo.name
        inner = "".join(
            f'  "{p.name}": "{"\\n".join([p.name, *wrapped(p)])}" {{ class: project; icon: {ICONS[p.kind]} }}\n'
            for p in own
        )
        return f'"{repo.name}": "{label}" {{\n  class: repository\n{inner}}}\n'

    def link(e: Edge) -> str:
        behind = e.version is not None and e.version != latest[e.target_repo]
        style = "behind" if behind else "pinned" if e.pinned else "tracking"
        return f"{e.source} -> {e.target}: {e.label} {{class: {style}}}\n"

    nodes = "".join(map(node, repos))
    links = "".join(
        link(e)
        for repo in repos
        for e in sorted(edges(found, repo), key=lambda e: (e.target, e.label))
    )
    return f"""vars: {{ d2-config: {{ layout-engine: elk }} }}
direction: down
classes: {{
  pinned: {{ style.stroke: "#333333"; style.font-size: 17 }}
  tracking: {{ style.stroke: "#333333"; style.stroke-dash: 4; style.font-size: 17 }}
  behind: {{ style.stroke: "#e00000"; style.font-size: 17 }}
  project: {{ width: 230; style.font-size: 16 }}
  standalone: {{ width: 230; style.font-size: 16 }}
  repository: {{ style.font-size: 20 }}
}}
{nodes}{links}"""


def wrapped(p: Project) -> list[str]:
    return textwrap.wrap(p.description, WRAP)


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
    lines = {line for repo in repos for p in projects(repo) for line in wrapped(p)}
    glyphs = "".join(sorted({c for line in lines for c in line if not c.isspace()}))
    # Hidden italic label, so the italic font embedded by D2 has every glyph of the descriptions
    source = d2(repos) + (
        f'glyphs: "{glyphs}" {{ near: bottom-right; shape: text; style: {{ italic: true; bold: false;'
        " font-size: 8; opacity: 0 } }\n"
    )
    drawn = subprocess.run(
        [*D2, "-", "-"], input=source, capture_output=True, text=True, check=False
    )
    if drawn.returncode != 0:
        sys.exit(drawn.stderr)
    output.write_text(italicise(drawn.stdout, lines))


if __name__ == "__main__":
    main()
