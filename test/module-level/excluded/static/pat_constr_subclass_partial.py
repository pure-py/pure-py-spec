# rule: def -- a subclass case leaves the base class's other instances, so the match
# is partial and the function may fall off the end
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Derived(Base):
    y: int

def f(v: Base) -> int:
    match v:
        case Derived(a, b):
            return b

print(f(Derived(1, 2)))
