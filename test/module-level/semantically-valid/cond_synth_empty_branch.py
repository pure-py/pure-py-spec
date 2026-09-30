# rule: cond-syn
def f(b: bool) -> int:
    return ([] if b else [1])[0]

print(f(False))
