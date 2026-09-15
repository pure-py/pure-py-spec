# rule: class-extend
from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    x: int  # PurePy: error (field clashes with inherited); Python: ok (override)

print("ok")
