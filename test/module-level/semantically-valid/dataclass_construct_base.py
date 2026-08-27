from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

b = Base(1)
print(b.x)
