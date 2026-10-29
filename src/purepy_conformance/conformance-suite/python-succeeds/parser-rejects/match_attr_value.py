from dataclasses import dataclass


@dataclass
class Colours:
    red: int
    blue: int


mod: Colours = Colours(1, 2)
v: int = 1
match v:
    case mod.red:
        print("red")
    case _:
        print("other")
