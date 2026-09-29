# rule: check-constr
from dataclasses import dataclass

@dataclass
class Box:
    x: int | None

def f(b: Box) -> int:
    match b:
        case Box(None):
            return 0
        case Box(n):
            return n + 1

print(f(Box(1)))
