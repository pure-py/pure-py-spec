# rule: pat-shapes -- the field grid spends the class, leaving nothing for a later class case
from dataclasses import dataclass

@dataclass
class Flags:
    x: bool
    y: bool

v = Flags(True, False)
match v:
    case Flags(True, True):
        print("tt")
    case Flags(True, False):
        print("tf")
    case Flags(False, True):
        print("ft")
    case Flags(False, False):
        print("ff")
    case Flags(a, b):  # PurePy: error (field space spent); Python: silently unreachable
        print(a)
        print(b)
