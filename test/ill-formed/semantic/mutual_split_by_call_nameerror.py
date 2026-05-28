# rule: var
def even(n):
    if n == 0:
        return True
    return odd(n - 1)

even(10)  # PurePy: error (intervening call splits mutual block); Python: NameError (odd undefined)

def odd(n):
    if n == 0:
        return False
    return even(n - 1)
