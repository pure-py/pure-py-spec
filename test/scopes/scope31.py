y = 7

def f():
    global y
    x = y # UnboundLocalError: cannot access local variable 'y'
    y = 8

f()
