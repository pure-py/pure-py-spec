# rule: split-list -- a list type has a shape for every length, so fixed-length
# patterns never exhaust it
def f(xs: list[int]) -> int:
    match xs:
        case []:
            return 0
        case [x]:
            return x

print(f([]))
