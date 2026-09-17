# rule: split-tuple
def f(t: tuple[int | str, int]) -> int:
    match t:
        case s:
            return s


print(f((1, 2)))
