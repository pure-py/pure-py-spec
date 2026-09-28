# rule: check-tuple-none
def f(t: tuple[int, int]) -> int:
    match t:
        case (a, b, c):
            return a
        case _:
            return 0


print(f((1, 2)))
