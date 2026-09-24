# rule: declare-assign
from dataclasses import dataclass


@dataclass
class C:
    n: int


C: int = 5
print(C + 1)
