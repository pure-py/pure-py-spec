# judgement: synth, rule: subscript-dict
def f(v: list[int] | dict[str, int]) -> int:
    return v[0]

print(f([1]))
