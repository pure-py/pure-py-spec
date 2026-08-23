# rule: class -- classes are declared by the module-statement judgement, not within a block
from dataclasses import dataclass
from typing import Any

def f():
    @dataclass
    class C:
        a: Any
    return 0

print("ok")
