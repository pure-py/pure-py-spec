# rule: subty-union
def f(v: int | str) -> float | str:
    return v

print(f(1))
print(f("a"))
