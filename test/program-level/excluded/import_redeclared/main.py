# rule: class
from dataclasses import dataclass
from m import C


@dataclass
class C:
    y: int


print(C(1).y)
