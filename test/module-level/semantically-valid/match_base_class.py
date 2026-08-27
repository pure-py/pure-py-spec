from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

b = Base(1)
match b:
    case Base(x):
        print(x)
    case _:
        print("other")
