# rule: assign
def f(v: int) -> int:
    match v:
        case y:
            def g() -> int:
                return y
    y = 2
    return g()

print(f(1))
