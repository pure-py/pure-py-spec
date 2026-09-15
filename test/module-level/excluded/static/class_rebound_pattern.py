# rule: top-seq -- a top-level capture pattern cannot take a class's name
from dataclasses import dataclass


@dataclass
class C:
    n: int


match 5:
    case C:
        print(C)
