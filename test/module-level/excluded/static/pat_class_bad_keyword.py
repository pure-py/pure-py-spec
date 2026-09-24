# rule: pat-constr
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

# Subject not a Point, so no runtime keyword lookup, on which CPython and GraalPy differ
p: None = None
match p:
    case Point(x=a, z=b):
        pass
    case _:
        pass
