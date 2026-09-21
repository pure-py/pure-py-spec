# rule: class
from dataclasses import dataclass

x: int = 1

def f() -> int:
    return x

@dataclass
class x:
    y: int

print("ok")
