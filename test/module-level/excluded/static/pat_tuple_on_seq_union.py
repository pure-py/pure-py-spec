# rule: match-case -- a tuple pattern is not sequence-safe at a union with a list member
def f(s: list[int] | tuple[int, int]) -> int:
    match s:
        case (a, b):
            return a
        case _:
            return 0


print(f([1, 2]))
