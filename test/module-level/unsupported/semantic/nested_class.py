# rule: block (block-wf has no class rule; dataclasses only at module top level)
from dataclasses import dataclass
from typing import Any

def f():
    @dataclass
    class C:
        a: Any
    return 0

print("ok")
