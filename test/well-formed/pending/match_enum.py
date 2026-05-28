from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2

c = Color.RED
match c:
    case Color.RED:
        print("red")
    case _:
        print("other")
