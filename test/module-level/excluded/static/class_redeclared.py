# rule: top-seq -- a class binding is permanent, so a name cannot be freed for redeclaration
from dataclasses import dataclass


@dataclass
class C:
    n: int


C = 5


@dataclass
class C:
    s: str


print(C("x").s)
