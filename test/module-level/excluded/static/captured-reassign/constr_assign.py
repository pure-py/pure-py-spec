# rule: top-seq
from dataclasses import dataclass

@dataclass
class C:
    x: int

def mk() -> C:
    return C(1)

C = 5

print("ok")
