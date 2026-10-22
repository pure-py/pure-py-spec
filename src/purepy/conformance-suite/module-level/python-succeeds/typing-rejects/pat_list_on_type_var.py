# rule: check-list-none
def f[T](x: T) -> int:
    match x:
        case [a]:
            return 1
        case _:
            return 0


print(f([1]))
