from __future__ import annotations

import pathlib
import tomllib

from diagram.node.project import Project, required
from diagram.node.repository import Repository


class PythonProject(Project):
    """Project file at the repository root ignored without a build system, since it then only installs
    test tools for another kind of project"""

    file = "pyproject.toml"
    icon = "python.svg"

    @classmethod
    def recognise(cls, repo: Repository, path: pathlib.PurePath) -> Project | None:
        config = tomllib.loads((repo.path / path).read_text())
        if "build-system" not in config and path.parent == pathlib.PurePath("."):
            return None
        meta = config["project"]
        return cls(repo.name, meta["name"], required(meta.get("description"), path), path.parent)
