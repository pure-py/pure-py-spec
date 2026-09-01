# rule: split-subclass -- a subclass case leaves the base class's other instances
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Derived(Base):
    y: int

def describe(v: Base) -> int:
    match v:
        case Derived(a, b):
            return b
        case Base(a):
            return a

print(describe(Derived(1, 2)))
print(describe(Base(3)))
