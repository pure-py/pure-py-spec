# rule: sub-constr -- a subclass pattern is unreachable under a base-class pattern
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Derived(Base):
    y: int

v = Derived(1, 2)
match v:
    case Base(a):
        print("base")
        print(a)
    case Derived(a, b):  # PurePy: error (subsumed by previous); Python: silently unreachable
        print("derived")
        print(a)
        print(b)
