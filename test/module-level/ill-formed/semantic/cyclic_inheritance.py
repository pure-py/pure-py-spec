# rule: class-extend
from dataclasses import dataclass
from typing import Any

@dataclass
class A(B):  # PurePy: error (cyclic inheritance); Python: NameError
    x: Any

@dataclass
class B(A):
    y: Any
