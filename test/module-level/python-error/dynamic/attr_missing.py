# attribute access on an object lacking the field. Python raises AttributeError;
# PurePy's eval-attr-missing aborts with AttributeError.
from dataclasses import dataclass
from typing import Any

@dataclass
class P:
    x: Any

print(P(1).y)
