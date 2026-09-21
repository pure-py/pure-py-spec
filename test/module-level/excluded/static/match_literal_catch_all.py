# rule: match
from typing import Literal
x: Literal[42] = 42
match x:
    case 42:
        print("forty-two")
    case _:
        print("other")
