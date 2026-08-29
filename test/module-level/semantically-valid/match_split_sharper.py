# rule: split-row -- splitting position by position exhausts what no single case covers
def f(p: tuple[bool, bool]) -> int:
    match p:
        case (True, _):
            return 1
        case (_, False):
            return 2
        case (False, True):
            return 3

print(f((True, False)))
print(f((False, False)))
print(f((False, True)))
