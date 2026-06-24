import mod

def f(v):
    match v:
        case mod.NotAClass():
            return 1
        case _:
            return 0

print(f(0))
