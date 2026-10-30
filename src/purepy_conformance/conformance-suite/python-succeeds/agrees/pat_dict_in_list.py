# rule: split-list
def f(xs: list[dict[str, int]]) -> int:
    match xs:
        case [{"a": n}]:
            return n
        case _:
            return 0


print(f([{"a": 1}]))
