# rule: call
def g() -> int:
    print("arg")
    return 3
x = 5
y = x(g())
