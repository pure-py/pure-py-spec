items: list[tuple[int, str]] = [(1, "a"), (2, "b")]
xs: list[int] = [a for a, b in items]
print(xs)
