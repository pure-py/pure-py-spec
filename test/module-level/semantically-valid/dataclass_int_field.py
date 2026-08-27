from dataclasses import dataclass

@dataclass
class C:
    x: int
print(C(1).x)
