# rule: sub-list-list / sub-tuple-tuple -- list and tuple patterns are distinct
# kinds, so neither subsumes the other (a list pattern matches only a list).
def f(s):
    match s:
        case [a, b]:
            return "list"
        case (c, d):
            return "tuple"
        case _:
            return "other"
print(f([1, 2]))
