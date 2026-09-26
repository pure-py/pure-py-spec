# rule: split-class
from dataclasses import dataclass

@dataclass
class Tree[T]:
    pass

@dataclass
class Either[S, T](Tree[S | T]):
    value: S

@dataclass
class FloatEither(Either[float, int]):
    pass

def first(t: Tree[float]) -> int:
    match t:
        case Either(v):
            return 1
        case Tree():
            return 0

print(first(FloatEither(1.5)))
