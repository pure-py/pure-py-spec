"""Classes, as Definition 2.2 gives them.

A class is identified by its qualified name, records the context it was declared
in, its own fields with their declared types, and its base class.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from type_syntax import Type

if TYPE_CHECKING:
    from contexts import Context


@dataclass(frozen=True, eq=False)
class Class:
    """A class, identified by its qualified name: two classes with the same
    name are the same class, and a class is also the type of its instances."""

    context: "Context"
    name: str
    own_fields: tuple[tuple[str, Type], ...]
    base: str | None

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Class) and self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __repr__(self) -> str:
        return f"Class({self.name})"


def short_name(c: Class) -> str:
    return c.name.rsplit(".", 1)[-1]


def ancestors(c: Class) -> list[Class]:
    if c.base is None:
        return [c]
    base = c.context[c.base]
    assert isinstance(base, Class)
    return [c] + ancestors(base)


def fields(c: Class) -> tuple[str, ...]:
    if c.base is None:
        return tuple(x for x, _ in c.own_fields)
    base = c.context[c.base]
    assert isinstance(base, Class)
    return fields(base) + tuple(x for x, _ in c.own_fields)


def field_type(c: Class, x: str) -> Type | None:
    """Declared type of field `x`, if the class records one."""
    own = dict(c.own_fields)
    if x in own:
        return own[x]
    if c.base is None:
        return None
    base = c.context[c.base]
    assert isinstance(base, Class)
    return field_type(base, x)


def field_map[T](
    c: Class,
    positional: Sequence[T],
    kwd_names: Sequence[str],
    kwd_values: Sequence[T],
) -> dict[str, T] | None:
    xs = fields(c)
    n = len(positional)
    if n + len(kwd_names) != len(xs) or len(set(kwd_names)) != len(kwd_names):
        return None
    if set(kwd_names) != set(xs[n:]):
        return None
    return {**dict(zip(xs[:n], positional)), **dict(zip(kwd_names, kwd_values))}
