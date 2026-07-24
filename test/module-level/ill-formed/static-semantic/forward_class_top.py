# rule: class (top-down, no forward refs at module top level)
from dataclasses import dataclass
from typing import Any

p = Point(1, 2)  # Point not yet declared

@dataclass
class Point:
    x: Any
    y: Any
