# rule: match-cases
from dataclasses import dataclass

@dataclass
class A:
    n: int

@dataclass
class B:
    s: str

def show(v: A | B) -> int | str:
    match v:
        case A(n=x):
            pass
        case B(s=x):
            pass
    return x

print(show(A(1)))
print(show(B("two")))
