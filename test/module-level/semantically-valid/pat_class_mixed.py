from dataclasses import dataclass

@dataclass
class Triple:
    x: int
    y: int
    z: int

t = Triple(1, 2, 3)
match t:
    case Triple(1, z=zz, y=yy):
        print(yy, zz)
    case _:
        print("other")
