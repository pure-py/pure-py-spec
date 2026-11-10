def f(p: tuple[int, int]) -> int:
    match p:
        case (a, a):
            return a
        case _:
            return 0


print(f((1, 2)))
