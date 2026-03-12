def foo(x):
    return x + 1
    return x  # PurePy: error (unreachable); Python: silently ignored

print(foo(5))
