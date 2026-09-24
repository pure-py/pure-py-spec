# rule: class
from dataclasses import dataclass

value: int = 1

@dataclass
class value:
    x: int

v: value = value(2)
print(v.x)
