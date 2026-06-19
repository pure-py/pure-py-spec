from dataclasses import dataclass
from typing import Any

@dataclass
class Pair:
    a: Any
    b: Any

p = Pair((1, [2, 3]), Pair(4, None))
match p:
    case Pair((1, [x, y]) as t, Pair(z, _)):
        print(t, x, y, z)
    case _:
        print("other")
