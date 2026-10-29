# rule: pat-literal-float
def f(x: int) -> int:
    match x:
        case 1.5:
            return 1
        case _:
            return 0


print(f(1))
