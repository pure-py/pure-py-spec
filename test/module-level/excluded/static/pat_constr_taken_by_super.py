# rule: pat-rest-constr -- a case for a class takes its subclasses, so a later
# case for a subclass matches nothing
from dataclasses import dataclass


@dataclass
class B:
    pass


@dataclass
class C(B):
    pass


@dataclass
class D(C):
    pass


def f(x: B) -> int:
    match x:
        case C():
            return 1
        case D():
            return 2
        case _:
            return 3


print(f(D()))
print(f(B()))
