# judgement: resolve-name
from dataclasses import dataclass

@dataclass
class C[T](T):
    pass
