def foo():
    x = y
    def bar():
        y = 10
        return y
    return bar()

y = 2
print(foo())