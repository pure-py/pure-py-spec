from dataclasses import dataclass
@dataclass
class P:
    x: int
p = P(1)
p.x = 2
print(p.x)
