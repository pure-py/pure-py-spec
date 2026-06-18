# rule: var
def even(n):
    if n == 0:
        return True
    return odd(n - 1)

x = even(0)  # PurePy: error (intervening call splits mutual block); Python: ok (late binding, doesn't reach odd)
print(x)

def odd(n):
    if n == 0:
        return False
    return even(n - 1)

print(even(10))
print(odd(10))
