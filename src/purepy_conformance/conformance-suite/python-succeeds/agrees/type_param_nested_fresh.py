# rule: def-signature
def f[A](x: A) -> int:
    def g[B](y: B) -> B:
        return y
    return g(1)


print(f("s"))
