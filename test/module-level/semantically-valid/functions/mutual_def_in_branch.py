b = True

if b:
    def f() -> str:
        return g()
    def g() -> str:
        return "via mutual region"
else:
    def f() -> str:
        return "f independent"
    def g() -> str:
        return "g independent"

print(f())
print(g())
