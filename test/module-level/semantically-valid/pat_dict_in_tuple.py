# rule: pat-tuple
def f(t: tuple[dict[str, int], int]) -> int:
    match t:
        case ({"a": n}, 1):
            return n
        case _:
            return 0


print(f(({"a": 1}, 1)))
