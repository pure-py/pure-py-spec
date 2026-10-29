# rule: class-extend
from dataclasses import dataclass
import builtins

@dataclass
class C(builtins.object):
    pass
