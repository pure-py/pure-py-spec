def outer(x):
    def middle(y):
        def inner(z):
            return x + y + z
        return inner
    return middle

print(outer(1)(2)(3))
