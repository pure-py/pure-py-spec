# rule: seq
from dataclasses import dataclass

@dataclass
class C:
    x: int

def mk() -> C:
    return C(1)

C = 5  # PurePy: error (C captured by mk, reassigned here); Python: rebinds C

print("ok")
