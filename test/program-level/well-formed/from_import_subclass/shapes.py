from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Derived(Base):
    y: Any
