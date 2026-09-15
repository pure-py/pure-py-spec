# rule: if-else -- branches assigning a class and its ancestor merge at the ancestor
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

def f(b: bool) -> Base:
    v: Base = Base(0)
    if b:
        v = Sub(1, 2)
    else:
        v = Base(3)
    w: Base = v
    return w

print(f(True).x)
print(f(False).x)
