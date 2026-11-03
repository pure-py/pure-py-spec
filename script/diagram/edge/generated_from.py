import re
from collections.abc import Iterator
from typing import Self

from diagram.edge import Edge
from diagram.node.isabelle_project import IsabelleProject
from diagram.node.python_project import PythonProject
from diagram.organisation import Organisation

VARIABLE = re.compile(r"^(?P<name>[A-Za-z_]\w*)\s*[:?]?=\s*(?P<value>.*)$", re.MULTILINE)
REFERENCE = re.compile(r"\$[({](?P<name>\w+)[)}]")
ISABELLE_BUILD = re.compile(r"\bisabelle\s+build\b")


def recipes(makefile: str) -> list[list[str]]:
    text = makefile.replace("\\\n", " ")
    variables = {m["name"]: m["value"].strip() for m in VARIABLE.finditer(text)}

    def expand(line: str, depth: int = 5) -> str:
        expanded = REFERENCE.sub(lambda m: variables.get(m["name"], m[0]), line)
        return expanded if depth == 0 or expanded == line else expand(expanded, depth - 1)

    rules: list[list[str]] = []
    for line in text.splitlines():
        if line.startswith("\t") and rules:
            rules[-1].append(expand(line.strip()))
        elif re.match(r"^[^\s#=][^=]*:(?!=)", line):
            rules.append([])
    return rules


class GeneratedFrom(Edge[PythonProject, IsabelleProject]):
    key = "Code generated from target"
    dash = 2

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Self]:
        for repo in org.repositories:
            makefile = repo.path / "Makefile"
            built = [p for p in org.projects[repo.name] if isinstance(p, IsabelleProject)]
            if not makefile.exists() or not built:
                continue
            for recipe in recipes(makefile.read_text()):
                start = next(
                    (i for i, line in enumerate(recipe) if ISABELLE_BUILD.search(line)), None
                )
                written = (
                    {word for line in recipe[start + 1 :] for word in line.split()}
                    if start is not None
                    else set()
                )
                for p in org.projects[repo.name]:
                    source = (p.directory / "src").as_posix()
                    if isinstance(p, PythonProject) and any(
                        w.startswith(source + "/") for w in written
                    ):
                        yield cls(p, built[0], "generated from")
