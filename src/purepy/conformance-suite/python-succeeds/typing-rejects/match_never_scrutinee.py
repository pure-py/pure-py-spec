# rule: pat-shapes
from typing import Never


def f(x: Never) -> int:
    match x:
        case _:
            return 0


print(0)
