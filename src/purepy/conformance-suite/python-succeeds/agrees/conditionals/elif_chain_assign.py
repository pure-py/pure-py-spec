# rule: if-else
def f(n: int) -> str:
    s: str
    if n == 0:
        s = "zero"
    elif n == 1:
        s = "one"
    else:
        s = "many"
    return s

print(f(0))
print(f(1))
print(f(2))
