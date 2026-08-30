# rule: pat-rest-constr -- a dictionary field takes its dictionary shape
from dataclasses import dataclass


@dataclass
class C:
    d: dict[str, int]


def f(c: C) -> int:
    match c:
        case C({"a": n}):
            return n
        case _:
            return 0


print(f(C({"a": 1})))
