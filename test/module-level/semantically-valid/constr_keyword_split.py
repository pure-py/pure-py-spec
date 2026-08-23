# rule: constr -- field-map accepts any split of the arguments that covers the fields
from dataclasses import dataclass
from typing import Any

@dataclass
class P:
    x: Any
    y: Any

def sum_of(p):
    match p:
        case P(a, b):
            return a + b

print(sum_of(P(1, 2)))
print(sum_of(P(1, y=2)))
print(sum_of(P(x=1, y=2)))
