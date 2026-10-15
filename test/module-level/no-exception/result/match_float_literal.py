# rule: pat-literal-float
def f(x: int | float) -> str:
    match x:
        case 1.5:
            return "a"
        case 2.5:
            return "b"
        case _:
            return "c"


def g(x: object) -> float:
    match x:
        case 1.5 as y:
            return y * 2
        case _:
            return 0.0


print(f(1.5))
print(f(2.5))
print(f(1))
print(g(1.5))
print(g("a"))
