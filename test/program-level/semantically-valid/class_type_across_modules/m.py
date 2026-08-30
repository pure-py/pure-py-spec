from dataclasses import dataclass

@dataclass
class C:
    x: int

def f(c: C) -> int:
    return c.x
