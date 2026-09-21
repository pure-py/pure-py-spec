from dataclasses import dataclass
from base import Base

@dataclass
class Derived(Base):
    y: int

d: Derived = Derived(1, 2)
print(d.x + d.y)
match d:
    case Base(x):
        print(x)
