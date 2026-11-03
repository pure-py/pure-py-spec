import pathlib
import textwrap
from dataclasses import dataclass
from typing import ClassVar

from diagram.node import Node
from diagram.node.repository import Repository

DESCRIPTION_WIDTH = 26


@dataclass(frozen=True)
class Project(Node):
    kinds: ClassVar[list[type["Project"]]] = []
    file: ClassVar[str]
    icon: ClassVar[str]
    description: str
    directory: pathlib.PurePath

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        Project.kinds.append(cls)

    @classmethod
    def recognise(cls, repo: Repository, path: pathlib.PurePath) -> "Project | None":
        raise NotImplementedError

    def lines(self) -> list[str]:
        return textwrap.wrap(self.description, DESCRIPTION_WIDTH)


def required(description: str | None, path: pathlib.PurePath) -> str:
    assert description, f"{path}: project has no description"
    return description
