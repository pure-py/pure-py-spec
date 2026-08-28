from dataclasses import dataclass

@dataclass
class Inner:
    a: int
    b: int

@dataclass
class Pair:
    a: tuple[int, list[int]]
    b: Inner

p = Pair((1, [2, 3]), Inner(4, 5))
match p:
    case Pair((1, [x, y]) as t, Inner(z, _)):
        print(t, x, y, z)
    case _:
        print("other")
