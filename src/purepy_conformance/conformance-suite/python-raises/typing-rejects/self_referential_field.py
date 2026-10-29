# rule: class
from dataclasses import dataclass

@dataclass
class Node:
    value: int
    next: Node | None

print(Node(1, None).value)
