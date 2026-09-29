# rule: syn-cond
from dataclasses import dataclass

@dataclass
class A:
    x: int

@dataclass
class B:
    y: int

def f(b: bool) -> int:
    return (A(1) if b else B(2)).x

print(f(True))
