# rule: pat-constr
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

# Subject isn't a Point: Python skips the keyword lookup; GraalPy doesn't
# propagate AttributeError. PurePy rejects the pattern statically regardless.
p = None
match p:
    case Point(x=a, z=b):  # PurePy: error ('z' not a field)
        pass
    case _:
        pass
