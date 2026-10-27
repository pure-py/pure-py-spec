# rule: binop
from dataclasses import dataclass
from typing import Callable

type A[T] = P[T] | None


@dataclass
class P[T]:
    rest: A[T]


type F = Callable[[int], int]

print(P[F](None) == P[F](None))
print(P[F](P[F](None)) == P[F](None))
