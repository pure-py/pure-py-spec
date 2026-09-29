# rule: subty-tuple
t: tuple[int, str] = (1, "a")
u: tuple[str, str] = t
print(u)
