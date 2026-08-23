from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Sub(Base):
    y: Any

s = Sub(1, 2)
print(s.x, s.y)
