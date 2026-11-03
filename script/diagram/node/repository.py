from __future__ import annotations

import pathlib
import subprocess
from dataclasses import dataclass

from diagram.node import Node

ORG = "pure-py"


@dataclass(frozen=True)
class Repository(Node):
    path: pathlib.Path
    version: str | None  # Latest release

    @classmethod
    def load(cls, path: pathlib.Path) -> Repository:
        view = subprocess.run(
            ["gh", "release", "view", "--repo", f"{ORG}/{path.name}", "--json", "tagName"]
            + ["--jq", ".tagName"],
            capture_output=True,
            text=True,
            check=False,
        )
        return cls(
            path.name, path.name, path, view.stdout.strip() if view.returncode == 0 else None
        )

    def files(self) -> list[pathlib.Path]:
        names = subprocess.run(
            ["git", "-C", self.path, "ls-files", "-z"], capture_output=True, check=True
        ).stdout
        return [self.path / name for name in names.decode().split("\0") if name]
