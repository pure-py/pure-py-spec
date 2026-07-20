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
    case Base(x):
        print(x)
    case _:
        print("other")
