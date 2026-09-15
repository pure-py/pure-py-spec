# rule: subty-callable -- parameters do not narrow
from typing import Callable

def f(n: int) -> int:
    return n

g: Callable[[float], int] = f  # PurePy: error (int parameter does not accept float); Python: runs
print(g(1.0))
