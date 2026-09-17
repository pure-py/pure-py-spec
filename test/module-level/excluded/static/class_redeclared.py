# rule: top-seq
from dataclasses import dataclass


@dataclass
class C:
    n: int


C = 5


@dataclass
class C:
    s: str


print(C("x").s)
