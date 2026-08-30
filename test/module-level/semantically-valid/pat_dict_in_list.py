# rule: pat-rest-list -- a list's element shapes come from shapes, a dictionary
# element taking its dictionary form
def f(xs: list[dict[str, int]]) -> int:
    match xs:
        case [{"a": n}]:
            return n
        case _:
            return 0


print(f([{"a": 1}]))
