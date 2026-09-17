# rule: top-seq
from dataclasses import dataclass


@dataclass
class C:
    n: int


C = 5
print(C + 1)
