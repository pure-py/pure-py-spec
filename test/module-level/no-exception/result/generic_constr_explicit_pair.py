from dataclasses import dataclass


@dataclass
class Pair[T, U]:
    left: T
    right: U


p: Pair[int, str] = Pair[int, str](1, "a")
print(p.left)
print(p.right)
