# rule: split-constr -- a base-class pattern splits a subclass shape at its own fields
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Derived(Base):
    y: int

def f(v: Base) -> int:
    match v:
        case Derived(1, b):
            return b
        case Base(a):
            return a

print(f(Derived(1, 2)))
print(f(Base(3)))
