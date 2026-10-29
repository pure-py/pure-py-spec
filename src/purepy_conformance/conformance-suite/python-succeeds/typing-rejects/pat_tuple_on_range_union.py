# rule: check-tuple-none
def f(x: tuple[int, int] | range) -> int:
    match x:
        case (a, b):
            return a + b
        case _:
            return 0


print(f(range(1, 3)))
