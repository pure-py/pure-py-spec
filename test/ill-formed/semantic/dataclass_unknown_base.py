# rule: class
from dataclasses import dataclass

@dataclass
class C(Missing):  # PurePy: error (base not declared); Python: NameError
    pass
