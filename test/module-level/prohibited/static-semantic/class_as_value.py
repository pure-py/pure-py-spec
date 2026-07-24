# rule: var -- a class name is not a first-class value (cf. module_as_value)
from dataclasses import dataclass
from typing import Any
@dataclass
class Point:
    x: Any
z = Point
