def foo():
    x = lambda: y
    y = 10  
    return x

print(foo()())
