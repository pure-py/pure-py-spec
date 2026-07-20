from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Sub(Base):
    y: Any

s = Sub(1, 2)
match s:
    case Base(x):  # matches: Sub derives from Base; binds Base's field
        print(x)
    case _:
        print("other")
