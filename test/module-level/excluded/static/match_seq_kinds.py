# rule: cases-cons -- a match on a union of list and tuple admits no sequence pattern
def f(s: list[int] | tuple[int, int]) -> str:
    match s:
        case [a, b]:
            return "list"
        case (c, d):
            return "tuple"
        case _:
            return "other"
print(f([1, 2]))
