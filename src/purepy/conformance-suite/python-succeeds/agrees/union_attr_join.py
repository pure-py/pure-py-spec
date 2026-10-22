# rule: attr-union
from dataclasses import dataclass


@dataclass
class A:
    x: int


@dataclass
class B:
    x: str


def f(v: A | B) -> int | str:
    return v.x


print(f(A(1)))
print(f(B("b")))
