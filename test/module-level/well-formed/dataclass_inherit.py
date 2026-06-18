from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Sub(Base):
    y: Any

print("ok")
