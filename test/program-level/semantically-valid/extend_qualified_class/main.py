from dataclasses import dataclass
import base

@dataclass
class Derived(base.Base):
    y: int

d: Derived = Derived(1, 2)
print(d.x + d.y)
match d:
    case base.Base(x):
        print(x)
