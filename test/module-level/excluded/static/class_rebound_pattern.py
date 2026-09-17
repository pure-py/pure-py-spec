# rule: top-seq
from dataclasses import dataclass


@dataclass
class C:
    n: int


match 5:
    case C:
        print(C)
