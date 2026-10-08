from dataclasses import dataclass

type Expr = Lit | Block
type Stmt = Print | Skip


@dataclass
class Lit:
    value: int


@dataclass
class Block:
    body: list[Stmt]
    result: Expr


@dataclass
class Print:
    arg: Expr


@dataclass
class Skip:
    pass


def count(e: Expr) -> int:
    match e:
        case Lit(_):
            return 1
        case Block(ss, r):
            return len(ss) + count(r)


print(count(Block([Print(Lit(1)), Skip()], Lit(2))))
