# rule: subscript-tuple -- a literal index must be in range
t: tuple[int, str] = (1, "a")
print(t[2])
