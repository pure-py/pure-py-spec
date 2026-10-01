from dataclasses import dataclass

@dataclass
class Circle:
    r: int

@dataclass
class Square:
    s: int

type Shape = Circle | Square
