# rule: constr -- field-map accepts any split of the arguments that covers the fields
from dataclasses import dataclass

@dataclass
class P:
    x: int
    y: int

def sum_of(p: P) -> int:
    match p:
        case P(a, b):
            return a + b
        case _:  # until exhaustiveness is checked, a match returns only with a catch-all
            return 0

print(sum_of(P(1, 2)))
print(sum_of(P(1, y=2)))
print(sum_of(P(x=1, y=2)))
