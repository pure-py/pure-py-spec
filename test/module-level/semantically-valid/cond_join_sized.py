# rule: cond-syn
def f(b: bool, xs: list[int]) -> int:
    return len(xs if b else "ab")

print(f(True, [1, 2, 3]))
print(f(False, [1, 2, 3]))
