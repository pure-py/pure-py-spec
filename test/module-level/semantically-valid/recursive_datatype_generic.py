from dataclasses import dataclass

type Tree[T] = Leaf[T] | Node[T]


@dataclass
class Leaf[T]:
    value: T


@dataclass
class Node[T]:
    left: Tree[T]
    right: Tree[T]


def size[T](t: Tree[T]) -> int:
    match t:
        case Leaf(_):
            return 1
        case Node(l, r):
            return size(l) + size(r)


t: Tree[int] = Node[int](Leaf(1), Node[int](Leaf(2), Leaf(3)))
print(size(t))
