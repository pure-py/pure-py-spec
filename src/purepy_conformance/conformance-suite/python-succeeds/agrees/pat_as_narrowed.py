# rule: check-as
from dataclasses import dataclass

@dataclass
class Box:
    x: int | None

def f(v: Box | None) -> Box:
    match v:
        case Box(None) as b:
            return b
        case Box(_) as b:
            return b
        case None:
            return Box(0)

print(f(None))
print(f(Box(1)))
