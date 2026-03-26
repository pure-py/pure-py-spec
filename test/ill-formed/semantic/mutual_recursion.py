def even(n):
    if n == 0:
        return True
    return odd(n - 1)

x = even(0)  # ok; doesn't call odd (late binding)
print(x)

def odd(n):
    if n == 0:
        return False
    return even(n - 1)

print(even(10))
print(odd(10))
