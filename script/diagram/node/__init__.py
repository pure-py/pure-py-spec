from dataclasses import dataclass

from diagram.registry import register


@dataclass(frozen=True)
class Node:
    repo: str
    name: str


register(__name__, __path__)
