# rule: binop -- tuple concatenation appends the component types
t: tuple[int, str] = (1,) + ("a",)
print(t)
