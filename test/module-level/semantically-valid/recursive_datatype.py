from dataclasses import dataclass

type Expr = Num | Add


@dataclass
class Num:
    value: int


@dataclass
class Add:
    left: Expr
    right: Expr


def evaluate(e: Expr) -> int:
    match e:
        case Num(n):
            return n
        case Add(l, r):
            return evaluate(l) + evaluate(r)


print(evaluate(Add(Num(1), Add(Num(2), Num(3)))))
