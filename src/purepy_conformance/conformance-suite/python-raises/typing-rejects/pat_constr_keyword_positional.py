# rule: check-constr
from dataclasses import dataclass


@dataclass
class P:
    x: int
    y: int


p: P = P(1, 2)
match p:
    case P(1, x=2):
        print("yes")
    case _:
        print("no")
