# rule: sub-list-list / sub-tuple-tuple -- empty list and tuple patterns are
# distinct kinds (an empty list pattern matches only an empty list).
def f(s: list[int] | tuple[()]) -> str:
    match s:
        case []:
            return "el"
        case ():
            return "et"
        case _:
            return "other"
print(f([]))
