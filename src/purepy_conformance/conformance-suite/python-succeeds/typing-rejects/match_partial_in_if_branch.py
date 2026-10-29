# rule: match-partial
def f(p: tuple[bool, bool], c: bool) -> int:
    if c:
        match p:
            case (True, True):
                return 1
            case (True, False):
                return 2
            case (False, True):
                return 3
            case (False, False):
                return 4
    else:
        return 0


print(f((True, False), True))
