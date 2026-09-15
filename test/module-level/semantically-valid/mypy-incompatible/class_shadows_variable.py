from dataclasses import dataclass

value = 1

@dataclass
class value:  # allowed: the name held a variable, not a class
    x: int

v = value(2)
print(v.x)
