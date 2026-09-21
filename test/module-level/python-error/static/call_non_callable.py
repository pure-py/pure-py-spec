# rule: call
def g() -> int:
    print("arg")
    return 3
x: int = 5
y: int = x(g())
