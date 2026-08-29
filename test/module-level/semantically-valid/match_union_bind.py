def f(xs: list[int] | list[str]) -> int | str:
    match xs:
        case [a]:
            return a
        case _:
            return 0

print(f([1]))
print(f(["a"]))
