# judgement: synth, rule: var
def f(v: list[int]) -> int:
    match v:
        case [x]:
            pass
        case _:
            pass
    return x


print(f([1]))
