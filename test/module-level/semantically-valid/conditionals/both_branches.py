def foo(a, b):
    if a < b:
        comp = "smaller"
    else:
        comp = "bigger"
    return comp

print(foo(1, 2))
print(foo(2, 1))
