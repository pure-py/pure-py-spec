# rule: class-extend
from dataclasses import dataclass

@dataclass
class Pair[A, B]:
    first: A
    second: B

@dataclass
class Named(Pair[str, int]):
    pass

n: Named = Named("a", 2)
print(n.first + "!")
print(n.second + 1)
