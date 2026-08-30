# rule: pat-list -- a list shape an earlier case left is matched position by position
def f(xs: list[int]) -> int:
    match xs:
        case [1, b]:
            return b
        case [a, 2]:
            return a
        case _:
            return 0

print(f([1, 5]))
print(f([7, 2]))
print(f([3, 3]))
