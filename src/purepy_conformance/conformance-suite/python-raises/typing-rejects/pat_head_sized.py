# judgement: check-pattern
from typing import Sized

match [1]:
    case Sized():
        print(0)
