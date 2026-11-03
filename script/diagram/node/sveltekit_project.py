import json
import pathlib

from diagram.node.project import Project, required
from diagram.node.repository import Repository


class SvelteKitProject(Project):
    file = "svelte.config.js"
    icon = "svelte.svg"

    @classmethod
    def recognise(cls, repo: Repository, path: pathlib.PurePath) -> Project | None:
        package = json.loads((repo.path / path.parent / "package.json").read_text())
        return cls(
            repo.name, package["name"], required(package.get("description"), path), path.parent
        )
