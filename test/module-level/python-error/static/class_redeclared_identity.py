# rule: declare-assign
from dataclasses import dataclass


@dataclass
class C:
    n: int


x: C = C(1)
C: int = 5


@dataclass
class C:
    s: str


y: C = x
print(y.s)
