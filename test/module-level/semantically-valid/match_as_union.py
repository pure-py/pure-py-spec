# rule: pat-as -- a named pattern binds at the join over the shapes it matched
def f(xs: list[int] | list[str]) -> list[int] | list[str]:
    match xs:
        case [_] as t:
            return t
        case _:
            return xs

print(f([1]))
print(f(["a", "b"]))
