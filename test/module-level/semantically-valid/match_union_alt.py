def f(xs: list[int] | list[str]) -> int:
    match xs:
        case ["a"]:
            return 1
        case _:
            return 0

print(f(["a"]))
print(f([1]))
