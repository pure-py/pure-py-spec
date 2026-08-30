# rule: subty-class
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

b: Base = Sub(1, 2)
print(b.x)
