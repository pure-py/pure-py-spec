# rule: check-tuple-none
def f[T](x: T) -> int:
    match x:
        case (a, b):
            return 1
        case _:
            return 0


print(f((1, 2)))
