# rule: assign
def f(b: bool) -> str:
    s: str
    if b:
        s = "yes"
    else:
        s = "no"
    return s

print(f(True))
print(f(False))
