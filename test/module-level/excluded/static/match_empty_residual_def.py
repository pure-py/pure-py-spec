# rule: match-partial
def f(t: tuple[bool, bool]) -> int:
    r: int
    match t:
        case (True, True):
            r = 0
        case (True, False):
            r = 1
        case (False, True):
            r = 2
        case (False, False):
            r = 3
    return r


print(f((True, False)))
