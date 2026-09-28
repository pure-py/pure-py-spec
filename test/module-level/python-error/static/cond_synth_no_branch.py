# rule: syn-cond
def f(b: bool) -> int:
    return ([] if b else [])[0]

print(f(True))
