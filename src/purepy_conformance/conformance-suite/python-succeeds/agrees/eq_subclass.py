# rule: binop
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

print(Base(1) == Sub(1, 2))
print(Sub(1, 2) != Base(1))
