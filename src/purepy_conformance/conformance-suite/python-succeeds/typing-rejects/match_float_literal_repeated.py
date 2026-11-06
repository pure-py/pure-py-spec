# judgement: match-set, rule: pat-shapes
def f(x: float) -> int:
    match x:
        case 1.5:
            return 1
        case 1.5:
            return 2
        case _:
            return 0


print(f(1.5))
