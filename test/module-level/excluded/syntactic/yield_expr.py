def gen() -> int:
    yield 1
    yield 2

print(list(gen()))
