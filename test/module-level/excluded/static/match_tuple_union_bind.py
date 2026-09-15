# rule: split-tuple -- a variable case binds at the tuple type itself
def f(t: tuple[int | str, int]) -> int:
    match t:
        case s:
            return s


print(f((1, 2)))
