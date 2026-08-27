# rule: seq
from dataclasses import dataclass

x = 1

def f():
    return x  # captures x (the variable)

@dataclass
class x:  # PurePy: error (x captured by f, reassigned here); Python: f sees this class
    y: int

print("ok")
