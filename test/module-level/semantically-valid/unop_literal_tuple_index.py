# rule: unop-literal
t: tuple[int, str] = (1, "a")
s: str = t[-1]
print(s)
