# rule: statement
from dataclasses import dataclass
from typing import Any

@dataclass
class C:
    x: Any

def mk():
    return C(1)

C = 5  # PurePy: error (C captured by mk, reassigned here); Python: rebinds C

print("ok")
