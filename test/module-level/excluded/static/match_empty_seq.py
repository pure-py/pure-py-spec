# rule: match
def f(s: list[int] | tuple[()]) -> str:
    match s:
        case []:
            return "el"
        case ():
            return "et"
        case _:
            return "other"
xs: list[int] = []
print(f(xs))
