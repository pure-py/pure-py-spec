from dataclasses import dataclass

@dataclass
class Pair:
    first: Item
    second: Item


@dataclass
class Item:
    value: int


print(Pair(Item(1), Item(2)).first.value)
