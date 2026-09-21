from dataclasses import dataclass

@dataclass
class Base:
    x: int

@dataclass
class Sub(Base):
    y: int

s: Sub = Sub(1)
