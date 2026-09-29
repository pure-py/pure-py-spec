# rule: check-constr
from dataclasses import dataclass

@dataclass
class P:
    x: int
    y: int

def f(v: P) -> int:
    match v:
        case P(x=a, x=b):
            return a
        case _:
            return 0

print(f(P(1, 2)))
