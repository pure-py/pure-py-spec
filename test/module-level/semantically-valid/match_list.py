def f(v: list[int]) -> int:
    match v:
        case [a, b]:
            return a + b
        case _:
            return 0

print(f([3, 4]))
