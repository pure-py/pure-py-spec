# rule: class-extend
from dataclasses import dataclass

@dataclass
class C(Missing):
    pass
