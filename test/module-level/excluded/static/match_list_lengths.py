# rule: split-list
def f(xs: list[int]) -> int:
    match xs:
        case []:
            return 0
        case [x]:
            return x

print(f([]))
