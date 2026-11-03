from collections.abc import Iterator
from typing import Self

from diagram.edge import Edge
from diagram.node.isabelle_project import IsabelleProject
from diagram.organisation import Organisation


class ImportsSession(Edge[IsabelleProject, IsabelleProject]):
    key = "Isabelle session import"
    dash = 2

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Self]:
        projects = [p for ps in org.projects.values() for p in ps if isinstance(p, IsabelleProject)]
        return (
            cls(importer, imported, "session import")
            for importer in projects
            for name in sorted(set(importer.imports) - set(importer.sessions))
            for imported in projects
            if imported.repo != importer.repo and name in imported.sessions
        )
