# rule: constr
from dataclasses import dataclass

@dataclass
class P:
    x: int
    y: str

p: P = P(y="b", x=1)
print(p.x)
print(p.y)
