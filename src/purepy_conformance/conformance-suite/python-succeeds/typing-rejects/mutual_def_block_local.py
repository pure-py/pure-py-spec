# rule: var
b: bool = True

if b:
    def f() -> str:
        return g()
    def g() -> str:
        return "g via mutual block"

print(g())
