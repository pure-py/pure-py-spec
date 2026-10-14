# rule: var
def f(n: int) -> int:
    if n == 0:
        return 0
    return g(n - 1)

c: int = 100

def g(n: int) -> int:
    if n == 0:
        return c
    return f(n - 1)

print(f(5))
