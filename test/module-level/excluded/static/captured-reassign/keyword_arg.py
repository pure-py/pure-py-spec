# rule: seq
from dataclasses import dataclass

@dataclass
class P:
    x: int

y = 1
def f() -> P:
    return P(x=y)
y = 2  # PurePy: error (y captured by f, reassigned here); Python: f sees this y
print(f().x)
