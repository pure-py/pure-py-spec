from dataclasses import dataclass

@dataclass
class Num:
    value: int


@dataclass
class Add:
    left: Expr
    right: Expr


type Expr = Num | Add
print(Add(Num(1), Num(2)).left)
