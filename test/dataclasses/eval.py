from dataclasses import dataclass

class Expr: ...

@dataclass
class IntExpr(Expr):
    val: int

@dataclass
class AddExpr(Expr):
    left: Expr
    right: Expr

def eval(e):
    match e:
        case IntExpr(i):
            return i
        case AddExpr(e1, e2):
            return eval(e1) + eval(e2)

print(eval(AddExpr(IntExpr(3), IntExpr(4))))
