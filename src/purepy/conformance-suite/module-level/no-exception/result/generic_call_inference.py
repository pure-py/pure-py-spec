from typing import Callable
from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


@dataclass
class IntBox(Box[int]):
    pass


def first[T](xs: list[T]) -> T:
    return xs[0]


def swap[A, B](p: tuple[A, B]) -> tuple[B, A]:
    return (p[1], p[0])


def apply[A, B](f: Callable[[A], B], x: A) -> B:
    return f(x)


def unbox[T](b: Box[T]) -> T:
    return b.value


def get[T](x: T | None, default: T) -> T:
    match x:
        case None:
            return default
        case y:
            return y


def same[T](x: T, y: T) -> T:
    return x


def inc(n: int) -> int:
    return n + 1


print(first([1, 2]))
print(swap((1, "a")))
print(apply(inc, 41))
print(unbox(IntBox(1)))
print(get(None, 0))
print(get(5, 0))
print(same(1, 2.5))
print(same(1, "a"))
