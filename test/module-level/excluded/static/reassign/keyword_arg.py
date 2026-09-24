# rule: assign
from dataclasses import dataclass

@dataclass
class P:
    x: int

y: int
y = 1
def f() -> P:
    return P(x=y)
y = 2
print(f().x)
