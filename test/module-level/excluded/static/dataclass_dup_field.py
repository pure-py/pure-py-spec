# rule: class
from dataclasses import dataclass

@dataclass
class C:
    x: int
    x: int  # PurePy: error (duplicate field); Python: ok (rebinds annotation)

print("ok")
