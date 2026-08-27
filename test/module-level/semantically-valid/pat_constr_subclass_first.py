# rule: sub-constr -- a base-class pattern is not subsumed by a subclass pattern
from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Derived(Base):
    y: Any

def describe(v: Any) -> Any:
    match v:
        case Derived(a, b):
            return b
        case Base(a):
            return a
        case _:
            return 0

print(describe(Derived(1, 2)))
print(describe(Base(3)))
