# rule: statement
from dataclasses import dataclass
from typing import Any

@dataclass
class C:
    x: Any

def mk():
    return C(1)

@dataclass
class C:  # PurePy: error (C captured by mk, re-declared here); Python: mk sees this class
    x: Any

match mk():
    case C(x):
        print(x)
    case _:
        print("other")
