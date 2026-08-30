# rule: cases-cons -- a component pattern agrees at the component's type
def f(t: tuple[list[str], int] | tuple[tuple[int, int], int]) -> int:
    match t:
        case ([a, b], n):
            return len(a) + n
        case _:
            return 0


print(f(((1, 2), 3)))
