# rule: constr
from dataclasses import dataclass
from typing import Any

@dataclass
class Point:
    x: Any
    y: Any

p = Point(1)  # PurePy: error (arity mismatch); Python: TypeError
