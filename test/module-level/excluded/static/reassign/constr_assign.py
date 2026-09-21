# rule: assign-annot
from dataclasses import dataclass

@dataclass
class C:
    x: int

def mk() -> C:
    return C(1)

C: int = 5

print("ok")
