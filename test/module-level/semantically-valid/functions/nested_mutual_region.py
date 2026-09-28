# rule: def
def outer(n: int) -> bool:
    def even(k: int) -> bool:
        if k == 0:
            return True
        return odd(k - 1)
    def odd(k: int) -> bool:
        if k == 0:
            return False
        return even(k - 1)
    return even(n)

print(outer(10))
print(outer(7))
