# rule: pat-shapes
def f(v: list[int] | tuple[int, int]) -> int:
    match v:
        case {"k": x}:
            return x
        case _:
            return 0

print(f([1]))
