# rule: binop
from dataclasses import dataclass
from typing import Callable

type A[T] = R[Callable[[], T]] | None


@dataclass
class R[T]:
    x: T
    r: A[T]


print(R[int](1, None) == R[int](1, None))
