# rule: call-stmt
from typing import Callable

def hello() -> None:
    pass

def run(f: Callable[[], None]) -> None:
    f()

run(hello)
print("done")
