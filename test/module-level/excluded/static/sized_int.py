# rule: subty-sized -- an int is not below Sized
from typing import Sized

x: Sized = 5  # PurePy: error (int has no length); Python: runs
print(x)
