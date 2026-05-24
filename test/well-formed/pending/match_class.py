from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(0, 1)
match p:
    case Point(x, y):
        print(x, y)
    case _:
        print("other")
