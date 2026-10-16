# rule: match-case
def f(v: int) -> int:
    match v:
        case x:
            pass
    return x


print(f(7))
