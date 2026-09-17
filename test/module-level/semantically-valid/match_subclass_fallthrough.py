from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

b = Base(1)
match b:
    case Sub(x, y):
        print(x)
        print(y)
    case _:
        print("other")
