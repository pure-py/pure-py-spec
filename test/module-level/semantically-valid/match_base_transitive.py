from dataclasses import dataclass
from typing import Any

@dataclass
class A:
    x: Any

@dataclass
class B(A):
    y: Any

@dataclass
class C(B):
    z: Any

v = C(1, 2, 3)
match v:
    case A(x):  # matches: C derives from A via B
        print(x)
    case _:
        print("other")
