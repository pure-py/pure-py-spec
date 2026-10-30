# rule: binop
from dataclasses import dataclass
from typing import Callable

type OptionalB[T] = B[T] | None


@dataclass
class A[T]:
    b: OptionalB[T]


@dataclass
class B[T]:
    a: A[T]


type F = Callable[[int], int]

print(A[F](None) == A[F](B[F](A[F](None))))
print(A[F](B[F](A[F](None))) == A[F](B[F](A[F](None))))
