# judgement: check-pattern, rule: check-var
from dataclasses import dataclass


@dataclass
class C:
    n: int


match 5:
    case C:
        print(C)
