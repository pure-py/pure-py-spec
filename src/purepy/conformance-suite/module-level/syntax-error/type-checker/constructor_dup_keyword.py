# rule: constr
from dataclasses import dataclass


@dataclass
class P:
    x: int


print(P(x=1, x=2))
