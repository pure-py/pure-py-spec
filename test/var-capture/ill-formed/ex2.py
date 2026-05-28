def foo():
    x = y
    y = 10          # Error
    return x

y = 11
print(foo())
