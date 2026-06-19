from dataclasses import dataclass
from typing import Any

@dataclass
class Triple:
    x: Any
    y: Any
    z: Any

t = Triple(1, 2, 3)
match t:
    case Triple(1, z=zz, y=yy):
        print(yy, zz)
    case _:
        print("other")
