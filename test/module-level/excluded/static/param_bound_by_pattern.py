# rule: def
def f(x: int, xs: list[int]) -> int:
    match xs:
        case [x]:
            return x
        case _:
            return 0


print(f(1, [2]))
