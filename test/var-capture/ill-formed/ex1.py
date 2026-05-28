def foo():
    y = 11
    def bar():
        return y
    y = 2
    return bar()