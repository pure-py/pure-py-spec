# rule: pat-shapes
from dataclasses import dataclass

@dataclass
class Flags:
    x: bool
    y: bool

v: Flags = Flags(True, False)
match v:
    case Flags(True, True):
        print("tt")
    case Flags(True, False):
        print("tf")
    case Flags(False, True):
        print("ft")
    case Flags(False, False):
        print("ff")
    case Flags(a, b):
        print(a)
        print(b)
