# rule: pat-class
from dataclasses import dataclass
from typing import Any

@dataclass
class Point:
    x: Any
    y: Any

# Subject isn't a Point: Python skips the keyword lookup; GraalPy doesn't
# propagate AttributeError. PurePy rejects the pattern statically regardless.
p = None
match p:
    case Point(x=a, z=b):  # PurePy: error ('z' not a field)
        pass
    case _:
        pass
