# rule: match-partial
def f(t: tuple[bool, bool]) -> int:
    match t:
        case (True, True):
            return 0
        case (False, False):
            return 1
        case (True, False):
            return 2
        case (False, True):
            return 3


print(f((True, False)))
