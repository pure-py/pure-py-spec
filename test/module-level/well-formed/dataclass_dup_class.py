from dataclasses import dataclass

@dataclass
class C:
    pass

@dataclass
class C:  # second declaration shadows the first (matches Python)
    pass

print("ok")
