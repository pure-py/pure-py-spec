# rule: top-seq
from dataclasses import dataclass


@dataclass
class C:
    n: int


def C() -> int:
    return 1


print(C())
