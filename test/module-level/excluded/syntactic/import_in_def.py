def f() -> list[str]:
    import sys
    return sys.argv

print(f() != "")
