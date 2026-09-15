# rule: class-extend
from dataclasses import dataclass

@dataclass
class C(Missing):  # PurePy: error (base not a class); Python: NameError
    pass
