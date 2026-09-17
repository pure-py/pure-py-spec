# rule: if-else
def f(b: bool) -> int | str:
    if b:
        x = 1
    else:
        x = "a"  # mypy: incompatible with the int declared by the first branch
    return x

print(f(True))
print(f(False))
