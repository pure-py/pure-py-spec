# rule: def -- a function declaring a result must definitely return one
def f(b: bool) -> int:
    if b:
        return 1

print(f(True))
