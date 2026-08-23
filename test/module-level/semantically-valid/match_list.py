def f(v):
    match v:
        case [a, b]:
            return a + b
        case _:
            return 0

print(f([3, 4]))
