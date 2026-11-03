from collections.abc import Iterator
from typing import Self

from diagram.edge import Edge
from diagram.node import Node
from diagram.organisation import Organisation
from diagram.reference import references


class Tracks(Edge[Node, Node]):
    key = "Follows target"
    dash = 4

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Self]:
        return (cls(r.source, r.target, r.label) for r in references(org) if not r.pinned)
