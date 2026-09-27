# rule: match
def f(b: bool) -> int:
    match b:
        case True:
            return 1
        case False:
            return 0


print(f(True))
print(f(False))
