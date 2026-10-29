# rule: split-class
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Derived(Base):
    y: int

v: Derived = Derived(1, 2)
match v:
    case Base(a):
        print("base")
        print(a)
    case Derived(a, b):
        print("derived")
        print(a)
        print(b)
