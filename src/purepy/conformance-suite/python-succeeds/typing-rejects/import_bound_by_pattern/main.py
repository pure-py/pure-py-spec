# rule: module
from m import x

match [1]:
    case [x]:
        print(x)
    case _:
        print(0)
