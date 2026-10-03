from dataclasses import dataclass

@dataclass
class Derived(Base):
    extra: int


@dataclass
class Base:
    value: int


print(Derived(1, 2).extra)
