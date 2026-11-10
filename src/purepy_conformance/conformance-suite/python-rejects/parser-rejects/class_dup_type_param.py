from dataclasses import dataclass

@dataclass
class C[T, T]:
    x: T

print("ok")
