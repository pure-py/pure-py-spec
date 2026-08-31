# rule: top-seq -- a class binding is permanent at the top level
from dataclasses import dataclass


@dataclass
class C:
    n: int


C = 5
print(C + 1)
