# rule: subty-tuple
t: tuple[int, str] = (1, "a")
u: tuple[int, str, int] = t
print(u)
