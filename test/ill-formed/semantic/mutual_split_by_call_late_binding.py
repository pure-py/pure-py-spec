def even(n):
    if n == 0:
        return True
    return odd(n - 1)

# ok in Python; doesn't call odd (late binding)
# but we will probably reject under any formulation of mutual recursion because statically even uses odd
x = even(0)
print(x)

def odd(n):
    if n == 0:
        return False
    return even(n - 1)

print(even(10))
print(odd(10))
