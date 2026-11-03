import pathlib
from dataclasses import dataclass

from diagram.node import Node
from diagram.node.project import Project
from diagram.node.repository import Repository


@dataclass(frozen=True, eq=False)
class Organisation:
    repositories: list[Repository]
    projects: dict[str, list[Project]]

    @classmethod
    def load(cls, root: pathlib.Path) -> "Organisation":
        repositories = [Repository.load(p) for p in sorted(root.iterdir()) if (p / ".git").exists()]
        kinds = {kind.file: kind for kind in Project.kinds}
        found = {
            repo.name: [
                kinds[path.name].recognise(repo, path.relative_to(repo.path))
                for path in repo.files()
                if path.name in kinds
            ]
            for repo in repositories
        }
        return cls(repositories, {name: [p for p in ps if p] for name, ps in found.items()})

    def repository(self, name: str) -> Repository | None:
        return next((r for r in self.repositories if r.name == name), None)

    def node_id(self, node: Node) -> str:
        """Repository, or project within a repository holding several"""
        if isinstance(node, Project) and len(self.projects[node.repo]) > 1:
            return f'"{node.repo}"."{node.name}"'
        return f'"{node.repo}"'

    def owner(self, repo: Repository, path: pathlib.PurePath) -> Node:
        """Project in the deepest directory containing a file, where a project at the repository root owns
        only its own project file; otherwise the repository"""
        owners = [
            p
            for p in self.projects[repo.name]
            if path == p.directory / p.file
            or (p.directory != pathlib.PurePath(".") and p.directory in path.parents)
        ]
        return max(owners, key=lambda p: len(p.directory.parts), default=repo)
