# rule: def-body
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
        pass


print(f((True, False), True))
