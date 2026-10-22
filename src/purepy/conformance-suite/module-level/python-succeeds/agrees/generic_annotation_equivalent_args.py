# rule: subty-class
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class Either(Box[int | str]):
    pass

def unbox(b: Box[str | int]) -> Box[str | int]:
    return b

x: Box[str | int] = unbox(Either(1))
print(x == Either(1))
