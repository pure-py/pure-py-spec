# attribute access on an object lacking the field. Python raises AttributeError;
# PurePy's eval-attr-missing aborts with AttributeError.
from dataclasses import dataclass

@dataclass
class P:
    x: int

print(P(1).y)
