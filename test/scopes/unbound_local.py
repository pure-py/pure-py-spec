y = 7

def f():
    x = y  # UnboundLocalError: y is local due to assignment below
    y = 8

f()
