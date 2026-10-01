# rule: split-literal
def f(x: float) -> int:
    match x:
        case 1:
            return 1
        case _:
            return 0


print(f(1.0))
print(f(2.5))
