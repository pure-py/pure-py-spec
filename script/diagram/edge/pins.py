from collections.abc import Iterator
from dataclasses import dataclass
from typing import Self

from diagram.edge import RED, Edge
from diagram.node import Node
from diagram.organisation import Organisation
from diagram.reference import references


@dataclass(frozen=True)
class Pins(Edge[Node, Node]):
    key = "Pin (moved by hand)"
    states = (("Pin behind latest release", RED),)
    outdated: bool = False

    @classmethod
    def find(cls, org: Organisation) -> Iterator[Self]:
        for r in references(org):
            if r.pinned:
                latest = org.repository(r.target.repo)
                outdated = (
                    r.version is not None and latest is not None and r.version != latest.version
                )
                yield cls(r.source, r.target, r.label, outdated)

    def colour(self) -> str:
        return RED if self.outdated else super().colour()
