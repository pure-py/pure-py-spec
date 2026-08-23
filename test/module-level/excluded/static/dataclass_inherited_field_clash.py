# rule: class
from dataclasses import dataclass
from typing import Any

@dataclass
class Base:
    x: Any

@dataclass
class Sub(Base):
    x: Any  # PurePy: error (field clashes with inherited); Python: ok (override)

print("ok")
