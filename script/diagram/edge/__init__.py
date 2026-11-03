from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar

from diagram.node import Node
from diagram.organisation import Organisation
from diagram.registry import register

BLACK = "#333333"
RED = "#e00000"


@dataclass(frozen=True)
class Style:
    key: str  # Text in the key of the diagram
    colour: str = BLACK
    dash: int = 0


@dataclass(frozen=True)
class Edge[S: Node, T: Node]:
    """Dependency of the source node on the target"""

    kinds: ClassVar[list[type["Edge[Any, Any]"]]] = []
    styles: ClassVar[tuple[Style, ...]]  # One for each state of an edge of the kind
    source: S
    target: T
    label: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        Edge.kinds.append(cls)

    @classmethod
    def find(cls, org: Organisation) -> Iterator["Edge[Any, Any]"]:
        raise NotImplementedError

    def style(self) -> Style:
        return self.styles[0]


register(__name__, __path__)
