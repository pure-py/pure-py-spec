# rule: check-constr
from dataclasses import dataclass


@dataclass
class P:
    x: int


v: P = P(1)
match v:
    case P(a, b):
        print(a)
    case _:
        print("no")
