xs: list[int] = [1, 2, 3, 2, 1]
s: set[int] = {x + 1 for x in xs}
print(s)
