# rule: attr-union
from dataclasses import dataclass

@dataclass
class A:
    x: int

@dataclass
class B:
    x: int

def f(v: A | B) -> int:
    return v.x

print(f(A(1)))
print(f(B(2)))
