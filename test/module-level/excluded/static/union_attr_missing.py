# rule: attr-union
from dataclasses import dataclass

@dataclass
class A:
    x: int

@dataclass
class B:
    y: int

def f(v: A | B) -> int:
    return v.x

print(f(A(1)))
