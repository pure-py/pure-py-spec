# rule: qual-generator
t: tuple[int, str] = (1, "a")
ys: list[int | str] = [x for x in t]
print(ys)
