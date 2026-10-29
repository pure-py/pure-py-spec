# rule: ty-class
from dataclasses import dataclass

type Boxes = Box[int]

@dataclass
class Box[T]:
    x: T

b: Boxes = Box(1)
print(b.x)
