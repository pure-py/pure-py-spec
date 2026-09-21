# rule: assign
def f(x: int) -> int:
    a: int = x
    x = 5
    b: int = x
    return a + b

print(f(10))
