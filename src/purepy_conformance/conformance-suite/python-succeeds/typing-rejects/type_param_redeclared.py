# rule: def-signature
def f[A](x: A) -> int:
    def g[A](y: A) -> A:
        return x
    return g(1) + 1


print(f(1))
