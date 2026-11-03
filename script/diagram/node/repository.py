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

    def text_files(self) -> list[pathlib.Path]:
        entries = subprocess.run(
            ["git", "-C", self.path, "ls-files", "--eol", "-z"], capture_output=True, check=True
        ).stdout
        return [
            self.path / name
            for eol, name in (
                entry.split("\t", 1) for entry in entries.decode().split("\0") if entry
            )
            if not eol.startswith("i/-text")
        ]
