def f(v):
    match v:
        case (x, y):
            r = x + y
        case _:
            return -1
    return r

print(f((1, 2)))
print(f(0))
