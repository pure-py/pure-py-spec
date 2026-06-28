# rule: class
from dataclasses import dataclass
from typing import Any

@dataclass
class C:
    x: Any
    x: Any  # PurePy: error (duplicate field); Python: ok (rebinds annotation)

print("ok")
