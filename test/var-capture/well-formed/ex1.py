def foo():
    y = x
    def bar():
        return y
    return bar()

x = 10
print(foo())