# judgement: synth, rule: binop
def f(x: int | None) -> int:
    return x + 1


print(f(None))
