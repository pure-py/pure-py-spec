from dataclasses import dataclass

@dataclass
class A:
    n: int

@dataclass
class B:
    s: str

def show(v: A | B) -> None:
    match v:
        case A(n=x):
            print("A")
        case B(s=x):
            print("B")
    print(x)

show(A(1))
show(B("two"))
