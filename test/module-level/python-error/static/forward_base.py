# rule: class-extend
from dataclasses import dataclass

@dataclass
class Sub(Base):
    y: int

@dataclass
class Base:
    x: int

print(Sub(1, 2).y)
