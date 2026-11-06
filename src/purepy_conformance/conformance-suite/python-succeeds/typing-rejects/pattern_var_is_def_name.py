# judgement: check-pattern, rule: check-var
def f() -> int:
    return 1


v: int = 2
match v:
    case f:
        print(f)
