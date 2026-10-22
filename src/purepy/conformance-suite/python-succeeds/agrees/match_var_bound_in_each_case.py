# rule: match-cases
def f(v: tuple[int, int]) -> int:
    match v:
        case (x, 0):
            pass
        case (_, x):
            pass
    return x


print(f((1, 0)))
print(f((1, 2)))
