# rule: def
from dataclasses import dataclass


@dataclass
class P:
    v: int


def f(p: P | None) -> int:
    match p:
        case P(x):
            return x
        case _:
            x: int = 0
            return x


print(f(P(3)))
print(f(None))
