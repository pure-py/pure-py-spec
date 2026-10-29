# rule: call
def push[T](xs: list[T], x: T) -> list[T]:
    return xs + [x]


xs: list[int] = [1]
print(push(xs, 2.5))
