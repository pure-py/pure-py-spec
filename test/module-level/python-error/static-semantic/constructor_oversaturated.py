# rule: constr -- too many positional arguments
from dataclasses import dataclass
from typing import Any
@dataclass
class Point:
    x: Any
    y: Any
p = Point(1, 2, 3)
