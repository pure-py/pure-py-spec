from dataclasses import dataclass

@dataclass
class C:
    a: int
    b: int

p: C = C(1, 2)
match p:
    case C(x, x):
        pass
