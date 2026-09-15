# rule: ty-callable -- Callable must be imported to be written
f: Callable[[int], int] = lambda x: x + 1
print(f(1))
