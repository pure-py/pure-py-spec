from dataclasses import dataclass
from typing import Any

@dataclass
class C:
    x: Any

a = C(1)

@dataclass
class C:  # PurePy: error (name already bound); Python: a remains an instance of the old class
    x: Any

match a:
    case C(x):
        print(x)
    case _:
        print("other")
