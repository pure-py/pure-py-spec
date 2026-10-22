# rule: pat-shapes
def f(b: bool) -> int:
    match b:
        case True:
            return 1
        case False:
            return 0
        case _:
            return 2


print(f(True))
