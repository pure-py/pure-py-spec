# rule: check-list-none
def f(x: list[int] | range) -> int:
    match x:
        case [a, b]:
            return a + b
        case _:
            return 0


print(f(range(1, 3)))
