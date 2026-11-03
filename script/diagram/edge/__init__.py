from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar, Self

from diagram import register
from diagram.node import Node
from diagram.organisation import Organisation

BLACK = "#333333"
RED = "#e00000"


@dataclass(frozen=True)
class Edge[S: Node, T: Node]:
    """Dependency of the source node on the target"""

    kinds: ClassVar[list[type["Edge[Any, Any]"]]] = []
    key: ClassVar[str]
    dash: ClassVar[int] = 0
    states: ClassVar[tuple[tuple[str, str], ...]] = ()  # Key text and colour of each state
    source: S
    target: T
    label: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        Edge.kinds.append(cls)

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Self]:
        raise NotImplementedError

    def colour(self) -> str:
        return BLACK


register(__name__, __path__)
