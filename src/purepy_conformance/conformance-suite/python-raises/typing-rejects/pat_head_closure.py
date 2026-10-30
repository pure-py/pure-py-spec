# rule: check-constr
def f(x: int) -> int:
    return x

match 1:
    case f():
        print(0)
