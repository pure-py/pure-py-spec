def f(**kw: int) -> int:
    return len(kw)


print(f(a=1, b=2))
