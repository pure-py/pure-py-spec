# rule: def-signature
def f[A](x: A) -> A:
    return x


def g[A](y: A) -> A:
    return y


print(f(1))
print(g("s"))
