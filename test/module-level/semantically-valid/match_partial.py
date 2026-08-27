from typing import Any
def f(v: Any) -> int:
    match v:
        case (x, y):
            return x + y
    return 0

print(f((1, 2)))
print(f(0))
