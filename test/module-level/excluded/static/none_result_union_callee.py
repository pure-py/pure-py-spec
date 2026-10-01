# rule: call-stmt
from typing import Callable

def foo() -> None:
    return

def bar() -> int:
    return 1

def pick(b: bool) -> Callable[[], None] | Callable[[], int]:
    return foo if b else bar

h: Callable[[], None] | Callable[[], int] = pick(True)
h()
print(1)
