# rule: type-alias
from dataclasses import dataclass

type MaybePoint = Point | None

print("split")

@dataclass
class Point:
    x: int

p: MaybePoint = None
print(p)
