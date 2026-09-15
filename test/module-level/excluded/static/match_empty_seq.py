# rule: match -- empty list and tuple patterns are sequence patterns too,
# so a union of the kinds admits neither
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
