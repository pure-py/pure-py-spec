from dataclasses import dataclass
from typing import Any

@dataclass
class P:
    x: Any
    y: Any

def f(v):
    match v:
        case P(x=a, x=b):
            return a
        case _:
            return 0

print(f(0))
