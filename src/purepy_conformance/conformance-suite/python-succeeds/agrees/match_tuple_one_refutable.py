# rule: match
def f(t: tuple[bool, int]) -> int:
    match t:
        case (True, 0):
            return 0
        case (False, _):
            return 1
        case (True, _):
            return 2


print(f((True, 0)))
print(f((False, 5)))
print(f((True, 5)))
