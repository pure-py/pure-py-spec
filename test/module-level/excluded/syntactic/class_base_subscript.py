from dataclasses import dataclass


@dataclass
class Base:
    value: int


@dataclass
class Derived(Base.__mro__[0]):
    pass


print(Derived(1))
