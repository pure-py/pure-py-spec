from dataclasses import dataclass
from typing import Any

def f():
    @dataclass
    class C:
        a: Any
    return 0

print("ok")
