# rule: subty-sized -- a list is below Sized
from typing import Sized

x: Sized = [1, 2]
print(len(x))
