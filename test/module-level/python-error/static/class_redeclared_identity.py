# rule: top-seq -- a class binding is permanent, so no second class can take its name
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
