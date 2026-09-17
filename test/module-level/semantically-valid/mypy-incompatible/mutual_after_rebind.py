def g() -> int:
    return 0

print(g())

def g() -> int:
    return h()
def h() -> int:
    return 1

print(g())
