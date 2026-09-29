# rule: ty-alias
from dataclasses import dataclass

type Num = int

@dataclass
class Box:
    n: Num

b: Box = Box(5)
print(b.n)
