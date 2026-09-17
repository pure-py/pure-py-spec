# rule: var
b = True

if b:
    def f() -> str:
        return g()
    def g() -> str:
        return "g via mutual block"
else:
    def f() -> str:
        return "f only"

print(g())
