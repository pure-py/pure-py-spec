# rule: pat-constr
from dataclasses import dataclass
@dataclass
class Empty:
    pass
e = Empty()
match e:
    case Empty():
        print("empty")
