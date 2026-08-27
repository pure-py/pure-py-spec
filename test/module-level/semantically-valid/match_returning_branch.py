from typing import Any
def f(v: Any) -> int:
    match v:
        case (x, y):
            r = x + y
        case _:
            return -1
    return r

print(f((1, 2)))
print(f(0))
