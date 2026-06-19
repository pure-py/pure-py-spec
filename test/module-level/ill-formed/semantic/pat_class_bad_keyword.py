# rule: pat-class
from dataclasses import dataclass
from typing import Any

@dataclass
class Point:
    x: Any
    y: Any

p = Point(1, 2)
match p:
    case Point(x=a, z=b):  # PurePy: error ('z' not a field); Python: AttributeError
        pass
