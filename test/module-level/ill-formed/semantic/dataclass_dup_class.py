# rule: class
from dataclasses import dataclass

@dataclass
class C:
    pass

@dataclass
class C:  # PurePy: error (duplicate class name); Python: ok (rebinds C)
    pass

print("ok")
