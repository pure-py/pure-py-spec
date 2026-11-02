from dataclasses import dataclass


@dataclass(frozen=True)
class P:
    x: int


print(P(1).x)
