# rule: top-seq -- a def region cannot take a class's name at the top level
from dataclasses import dataclass


@dataclass
class C:
    n: int


def C() -> int:
    return 1


print(C())
