# rule: def-body
def f(b: bool) -> int | None:
    if b:
        return 1

print(f(True))
