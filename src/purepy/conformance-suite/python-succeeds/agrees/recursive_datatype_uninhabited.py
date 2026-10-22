from dataclasses import dataclass

type Stream = Cons


@dataclass
class Cons:
    head: int
    tail: Stream


def first(s: Stream) -> int:
    return s.head


print("defined")
