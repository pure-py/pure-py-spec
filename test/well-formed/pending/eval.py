from dataclasses import dataclass
from typing import Any

@dataclass
class Expr:
    pass

@dataclass
class IntExpr(Expr):
    val: Any

@dataclass
class AddExpr(Expr):
    left: Any
    right: Any

def eval(e):
    match e:
        case IntExpr(i):
            return i
        case AddExpr(e1, e2):
            return eval(e1) + eval(e2)

print(eval(AddExpr(IntExpr(3), IntExpr(4))))
