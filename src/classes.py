from collections.abc import Sequence
from dataclasses import dataclass

from type_syntax import Type


@dataclass(frozen=True)
class Class:
    """A class, identified by its qualified name: two classes with the same
    name are the same class, and a class is also the type of its instances."""

    name: str

    def __repr__(self) -> str:
        return f"Class({self.name})"


@dataclass(frozen=True)
class ClassTableEntry:
    own_fields: tuple[tuple[str, Type], ...]
    base: Class | None


type ClassTable = dict[Class, ClassTableEntry]


def short_name(c: Class) -> str:
    return c.name.rsplit(".", 1)[-1]


def ancestors(sigma: ClassTable, c: Class) -> list[Class]:
    base = sigma[c].base
    return [c] if base is None else [c] + ancestors(sigma, base)


def fields(sigma: ClassTable, c: Class) -> tuple[str, ...]:
    entry = sigma[c]
    own = tuple(x for x, _ in entry.own_fields)
    return own if entry.base is None else fields(sigma, entry.base) + own


def field_type(sigma: ClassTable, c: Class, x: str) -> Type | None:
    """Declared type of field `x`, if the class records one."""
    entry = sigma[c]
    own = dict(entry.own_fields)
    if x in own:
        return own[x]
    return None if entry.base is None else field_type(sigma, entry.base, x)


def declared_type(sigma: ClassTable, c: Class, x: str) -> Type:
    """Declared type of field `x` of `c`."""
    t = field_type(sigma, c, x)
    assert t is not None
    return t


def field_map[T](
    sigma: ClassTable,
    c: Class,
    positional: Sequence[T],
    kwd_names: Sequence[str],
    kwd_values: Sequence[T],
) -> dict[str, T] | None:
    xs = fields(sigma, c)
    n = len(positional)
    if n + len(kwd_names) != len(xs) or len(set(kwd_names)) != len(kwd_names):
        return None
    if set(kwd_names) != set(xs[n:]):
        return None
    return {**dict(zip(xs[:n], positional)), **dict(zip(kwd_names, kwd_values))}
