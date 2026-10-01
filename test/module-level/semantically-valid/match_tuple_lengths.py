# rule: split-tuple
def f(t: tuple[int, int] | tuple[int, int, int]) -> int:
    match t:
        case (a, b):
            return a + b
        case (a, b, c):
            return a + b + c


print(f((1, 2)))
print(f((1, 2, 3)))
