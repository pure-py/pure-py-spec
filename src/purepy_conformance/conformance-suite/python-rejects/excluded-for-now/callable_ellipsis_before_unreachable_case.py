from typing import Callable

f: Callable[..., int] = lambda: 1
match f():
    case _:
        print("a")
    case 1:
        print("b")
