# rule: if-else -- branches assigning incomparable types merge at their union
def f(b: bool) -> int | str:
    if b:
        x = 1
    else:
        x = "a"
    y: int | str = x
    return y

print(f(True))
print(f(False))
