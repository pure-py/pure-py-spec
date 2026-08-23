from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Sub(Base):
    y: Any

b = Base(1)
print(b.x)
