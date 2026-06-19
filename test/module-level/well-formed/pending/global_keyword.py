y = 7

def f():
    global y
    x = y
    y = 8
    return x

print(f())  # 7: x captured global y before reassignment
print(y)    # 8: global y was updated by f
