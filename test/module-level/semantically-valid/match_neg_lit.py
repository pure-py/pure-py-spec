def f(x: int) -> str:
    match x:
        case -3:
            return "negative three"
        case _:
            return "other"


print(f(-3))
print(f(3))
