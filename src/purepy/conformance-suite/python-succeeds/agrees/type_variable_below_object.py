# rule: subty-object
def f[T](x: T) -> object:
    return x


print(f(1))
