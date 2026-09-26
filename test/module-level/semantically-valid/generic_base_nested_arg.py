# rule: class-extend
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class Boxes[T](Box[list[T]]):
    pass

@dataclass
class IntBoxes(Boxes[int]):
    pass

b: IntBoxes = IntBoxes([1, 2, 3])
print(len(b.value))
