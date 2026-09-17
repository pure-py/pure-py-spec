from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

s = Sub(1, 2)
match s:
    case Base(x):
        print(x)
