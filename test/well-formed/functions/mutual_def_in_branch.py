b = True

if b:
    def f():
        return g()
    def g():
        return "via mutual block"
else:
    def f():
        return "f independent"
    def g():
        return "g independent"

print(f())
print(g())
