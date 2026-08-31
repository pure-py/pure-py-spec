# rule: module -- a module declares each class name at most once
from dataclasses import dataclass


@dataclass
class C:
    n: int


C = 5


@dataclass
class C:
    s: str


print(C("x").s)
