# rule: head-class
from dataclasses import dataclass


@dataclass
class Base:
    x: int


@dataclass
class Derived(Base):
    y: int


def f(v: Base) -> int:
    match v:
        case Derived(a, 0):
            return 1
        case Base(0):
            return 2
        case Derived(a, 0):
            return 3
        case _:
            return 0


print(f(Derived(1, 2)))
