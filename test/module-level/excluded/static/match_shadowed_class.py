# rule: class
from dataclasses import dataclass

@dataclass
class C:
    x: int

a: C = C(1)

@dataclass
class C:
    x: int

match a:
    case C(x):
        print(x)
    case _:
        print("other")
