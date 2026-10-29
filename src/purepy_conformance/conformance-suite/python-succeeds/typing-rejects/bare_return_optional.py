# rule: return-none
def f(b: bool) -> int | None:
    if b:
        return 1
    return

print(f(True))
