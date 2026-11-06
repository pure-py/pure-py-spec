# judgement: stmt, rule: assign
from dataclasses import dataclass

@dataclass
class C:
    n: int

C = 5
print(C)
