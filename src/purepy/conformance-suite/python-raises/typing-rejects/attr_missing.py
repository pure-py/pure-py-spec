# rule: attr-object
from dataclasses import dataclass

@dataclass
class P:
    x: int

print(P(1).y)
