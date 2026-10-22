import builtins
import sys
from dataclasses import dataclass

@dataclass
class C:
    x: int

print(builtins.len([1, 2, 3]))
