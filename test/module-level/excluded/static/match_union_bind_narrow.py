# rule: split-shapes -- a variable binds at the join over the shapes matched
def f(xs: list[int] | list[str]) -> int:
    match xs:
        case [a]:
            return a
        case _:
            return 0

print(f([1]))
