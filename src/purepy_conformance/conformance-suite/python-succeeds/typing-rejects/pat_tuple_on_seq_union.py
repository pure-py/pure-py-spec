# rule: check-tuple-none
def f(s: list[int] | tuple[int, int]) -> int:
    match s:
        case (a, b):
            return a
        case _:
            return 0


print(f([1, 2]))
