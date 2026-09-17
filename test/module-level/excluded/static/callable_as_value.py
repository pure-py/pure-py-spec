# rule: var
from typing import Callable

x = Callable  # PurePy: error (not a value); Python: binds the typing object
print(x)
