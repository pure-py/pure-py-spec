# rule: split-constr -- field-map pairs fields, whatever the argument split
from dataclasses import dataclass

@dataclass
class P:
    x: int
    y: int

v = P(1, 2)
match v:
    case P(a, y=b):
        print("first")
        print(a)
        print(b)
    case P(x=1, y=2):  # PurePy: error (subsumed by previous); Python: silently unreachable
        print("second")
