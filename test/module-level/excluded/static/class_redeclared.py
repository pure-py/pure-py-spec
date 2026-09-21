# rule: assign-annot
from dataclasses import dataclass


@dataclass
class C:
    n: int


C: int = 5


@dataclass
class C:
    s: str


print(C("x").s)
