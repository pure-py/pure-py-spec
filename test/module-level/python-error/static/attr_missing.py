# rule: attr-object -- the field must be one the class declares
from dataclasses import dataclass

@dataclass
class P:
    x: int

print(P(1).y)
