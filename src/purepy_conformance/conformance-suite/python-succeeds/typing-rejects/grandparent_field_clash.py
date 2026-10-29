# rule: class-extend
from dataclasses import dataclass

@dataclass
class A:
    x: int

@dataclass
class B(A):
    y: int

@dataclass
class C(B):
    x: int

print("ok")
