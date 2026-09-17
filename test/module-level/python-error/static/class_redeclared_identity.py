# rule: top-seq
from dataclasses import dataclass


@dataclass
class C:
    n: int


x = C(1)
C = 5


@dataclass
class C:
    s: str


y: C = x
print(y.s)
