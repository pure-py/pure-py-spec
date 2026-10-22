# rule: subty-tuple
t: tuple[int, str] = (1, "a")
u: tuple[float, str] = t
print(u)
