# rule: top-seq -- reassigning the captured class name is now rejected as rebinding a class
from dataclasses import dataclass

@dataclass
class C:
    x: int

def mk() -> C:
    return C(1)

C = 5  # PurePy: error (C captured by mk, reassigned here); Python: rebinds C

print("ok")
