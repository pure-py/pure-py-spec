# rule: module -- two classes sharing a qualified name would be conflated
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
