# rule: var -- a class name is not a first-class value (cf. module_as_value)
from dataclasses import dataclass
@dataclass
class Point:
    x: int
z = Point
