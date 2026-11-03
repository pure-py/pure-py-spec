from __future__ import annotations

import importlib
import pathlib
import pkgutil
import textwrap
from dataclasses import dataclass
from typing import ClassVar

from diagram.node import Node
from diagram.node.repository import Repository

DESCRIPTION_WIDTH = 26


@dataclass(frozen=True)
class Project(Node):
    file: ClassVar[str]
    icon: ClassVar[str]
    description: str
    directory: pathlib.PurePath

    @classmethod
    def kinds(cls) -> list[type[Project]]:
        """Kinds of project, from the modules of the node package"""
        package = importlib.import_module("diagram.node")
        for module in pkgutil.iter_modules(package.__path__):
            importlib.import_module(f"diagram.node.{module.name}")
        return cls.__subclasses__()

    @classmethod
    def recognise(cls, repo: Repository, path: pathlib.PurePath) -> Project | None:
        raise NotImplementedError

    def lines(self) -> list[str]:
        return textwrap.wrap(self.description, DESCRIPTION_WIDTH)


def required(description: str | None, path: pathlib.PurePath) -> str:
    assert description, f"{path}: project has no description"
    return description
