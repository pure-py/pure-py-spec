# rule: check-tuple
def f(t: tuple[int | None, int]) -> int:
    match t:
        case (None, y):
            return y
        case (x, y):
            return x + y

print(f((1, 2)))
print(f((None, 3)))
