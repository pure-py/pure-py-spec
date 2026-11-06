# judgement: stmt, rule: declare-assign
t: tuple[int, str] = (1, "a")
n: int = t[-1]
print(n)
