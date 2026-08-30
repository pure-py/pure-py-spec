# rule: seq -- a pattern variable is in the function's scope, so a case body captures it like any other
def f(v: int) -> int:
    match v:
        case y:
            def g() -> int:
                return y
    y = 2  # PurePy: error (y captured by g, reassigned here); Python: g sees this y
    return g()

print(f(1))
