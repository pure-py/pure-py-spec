# rule: pat-shapes
def f(xs: list[int] | list[str]) -> int:
    match xs:
        case [a]:
            return a
        case _:
            return 0

print(f([1]))
