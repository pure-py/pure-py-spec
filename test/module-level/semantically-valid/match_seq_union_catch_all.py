def f(s: list[int] | tuple[int, int]) -> int:
    match s:
        case t:
            return len(t)


print(f([1, 2, 3]))
print(f((1, 2)))
