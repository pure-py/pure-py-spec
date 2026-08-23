# rule: sub-constr -- a subclass pattern is unreachable under a base-class pattern
from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Derived(Base):
    y: Any

v = Derived(1, 2)
match v:
    case Base(a):
        print("base", a)
    case Derived(a, b):  # PurePy: error (subsumed by previous); Python: silently unreachable
        print("derived", a, b)
