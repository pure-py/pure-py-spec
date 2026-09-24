# rule: match
from typing import Literal
x: Literal[42] = 42
y: str
match x:
    case 42:
        y = "yes"
print(y)
