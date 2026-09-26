# rule: class
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class Other:
    value: T
