# rule: if-else -- PurePy joins the branch types; mypy declares the variable from the first branch
def f(b: bool) -> int | str:
    if b:
        x = 1
    else:
        x = "a"  # mypy: incompatible with the int declared by the first branch
    return x

print(f(True))
print(f(False))
