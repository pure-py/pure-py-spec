# rule: top-seq -- a top-level pattern cannot take a class's name
from dataclasses import dataclass

@dataclass
class C:
    x: int

a = C(1)

@dataclass
class C:  # PurePy: error (name already bound); Python: a remains an instance of the old class
    x: int

match a:
    case C(x):
        print(x)
    case _:
        print("other")
