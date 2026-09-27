# rule: check-list-none
def f(o: object) -> int:
    match o:
        case [a, b]:
            return 1
        case _:
            return 0


print(f([1, 2]))
