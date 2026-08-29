# rule: pat-constr -- a constructor pattern for a zero-field class
from dataclasses import dataclass
@dataclass
class Empty:
    pass
e = Empty()
match e:
    case Empty():
        print("empty")
