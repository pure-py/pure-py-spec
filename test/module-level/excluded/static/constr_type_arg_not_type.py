# rule: constr-explicit
from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


print(Box[1 + 2](1).value)
