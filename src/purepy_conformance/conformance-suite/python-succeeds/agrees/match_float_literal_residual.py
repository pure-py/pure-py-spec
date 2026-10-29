# rule: pat-literal-float
def f(t: tuple[float, int]) -> int:
    match t:
        case (1.5, 0):
            return 1
        case (_, 0):
            return 2
        case _:
            return 3


print(f((1.5, 0)))
print(f((2.5, 0)))
print(f((2.5, 1)))
