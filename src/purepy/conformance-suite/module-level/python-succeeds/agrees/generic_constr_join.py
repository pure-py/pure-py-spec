from dataclasses import dataclass


@dataclass
class Pair[T]:
    left: T
    right: T


p: Pair[int | str] = Pair(1, "a")
print(p.left)
print(p.right)
