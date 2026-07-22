from dataclasses import dataclass
from typing import Any

value = 1

@dataclass
class value:  # PurePy: error (name already bound); Python: rebinds the name
    x: Any

print("ok")
