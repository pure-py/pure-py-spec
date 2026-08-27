from dataclasses import dataclass

def f():
    @dataclass
    class C:
        a: int
    return 0

print("ok")
