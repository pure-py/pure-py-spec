# rule: pat-constr
from dataclasses import dataclass
from typing import Any

@dataclass
class Point:
    x: Any
    y: Any

p = Point(1, 2)
match p:
    case Point():  # PurePy: error (under-saturated); Python: ok (matches any Point)
        pass
