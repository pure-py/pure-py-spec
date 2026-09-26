# rule: class-extend
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class Bad(Box):
    pass

print("ok")
