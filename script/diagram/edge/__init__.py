from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar

from diagram.node import Node
from diagram.organisation import Organisation

BLACK = "#333333"
RED = "#e00000"


@dataclass(frozen=True)
class Style:
    key_text: str
    colour: str = BLACK
    dash: int = 0


@dataclass(frozen=True)
class Edge[S: Node, T: Node]:
    """Dependency of source on target"""

    styles: ClassVar[tuple[Style, ...]]  # One for each state of an edge of the kind
    source: S
    target: T
    label: str

    @classmethod
    def kinds(cls) -> list[type[Edge[Any, Any]]]:
        """Kinds of edge defined in the modules of this package"""
        for module in pkgutil.iter_modules(__path__):
            importlib.import_module(f"{__name__}.{module.name}")
        return cls.__subclasses__()

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Edge[Any, Any]]:
        raise NotImplementedError

    def style(self) -> Style:
        return self.styles[0]
