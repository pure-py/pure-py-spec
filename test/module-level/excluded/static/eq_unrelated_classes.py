# rule: binop
from dataclasses import dataclass

@dataclass
class A:
    x: int

@dataclass
class B:
    x: int

print(A(1) == B(1))
