from dataclasses import dataclass

@dataclass
class A:
    x: int

@dataclass
class B(A):
    y: int

@dataclass
class C(B):
    z: int

v = C(1, 2, 3)
match v:
    case A(x):  # matches: C derives from A via B
        print(x)
