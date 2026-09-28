# rule: def-body
def f(b: bool, v: int) -> int:
    if b:
        match v:
            case x:
                return x
    x: int = 0
    return x

print(f(True, 1))
