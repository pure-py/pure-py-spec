# rule: seq
from dataclasses import dataclass

x = 1

def f() -> int:
    return x  # captures x (the variable)

@dataclass
class x:
    y: int

print("ok")
