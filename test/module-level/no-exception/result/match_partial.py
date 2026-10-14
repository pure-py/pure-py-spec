def f(v: tuple[int, int] | int) -> int:
    match v:
        case (x, y):
            return x + y
    return 0

print(f((1, 2)))
print(f(0))
