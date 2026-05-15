def f(n):
    if n == 0:
        return 0
    return g(n - 1)

# natural place to put a constant g uses, but this assignment splits
# what would otherwise be a contiguous mutual block of {f, g}
c = 100

def g(n):
    if n == 0:
        return c
    return f(n - 1)

print(f(5))
