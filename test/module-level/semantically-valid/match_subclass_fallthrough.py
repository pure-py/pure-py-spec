from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Sub(Base):
    y: Any

b = Base(1)
match b:
    case Sub(x, y):  # no match: Base does not derive from Sub
        print(x, y)
    case _:
        print("other")
