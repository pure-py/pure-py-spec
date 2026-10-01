# rule: class-extend
from dataclasses import dataclass

@dataclass
class Point:
    x: int

type P = Point

@dataclass
class Q(P):
    y: int

print(Q(1, 2).y)
