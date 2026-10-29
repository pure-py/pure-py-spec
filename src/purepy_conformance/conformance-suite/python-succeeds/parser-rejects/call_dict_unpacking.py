from dataclasses import dataclass

@dataclass
class P:
    x: int

d: dict[str, int] = {"x": 1}
print(P(**d))
