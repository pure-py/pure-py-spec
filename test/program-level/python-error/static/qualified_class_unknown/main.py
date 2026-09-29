import mod

def f(v: int) -> int:
    match v:
        case mod.NotAClass():
            return 1
        case _:
            return 0

print(f(0))
