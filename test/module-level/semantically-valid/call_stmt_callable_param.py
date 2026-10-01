# rule: call-stmt
from typing import Callable

def hello() -> None:
    print("hi")

def run(f: Callable[[], None]) -> None:
    f()

run(hello)
