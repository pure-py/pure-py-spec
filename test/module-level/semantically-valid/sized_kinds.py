# rule: subty-sized
from typing import Sized

a: Sized = "ab"
b: Sized = {"a": 1}
c: Sized = (1, 2)
print(len(a) + len(b) + len(c))
