# rule: var
y: int = 7

def f() -> None:
    x: int = y
    y: int = 8

f()
