# rule: callee-scheme
def wrap[T](x: T) -> list[T]:
    return [x]


xs: list[int] = wrap(1)
print(xs)
