def even(n):
    if n == 0:
        return True
    return odd(n - 1)

even(10)  # NameError: odd is not defined at call time

def odd(n):
    if n == 0:
        return False
    return even(n - 1)
