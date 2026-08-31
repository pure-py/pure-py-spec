# rule: assign -- a class name may be rebound; the class itself is unaffected
from dataclasses import dataclass


@dataclass
class C:
    n: int


C = 5
print(C + 1)
