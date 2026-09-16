from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from type_syntax import Type, Var


@dataclass(frozen=True)
class Class:
    name: str

    def __repr__(self) -> str:
        return f"Class({self.name})"


@dataclass(frozen=True)
class ClassTableEntry:
    own_fields: tuple[tuple[Var, Type], ...]
    base: Class | None


type ClassTable = Mapping[Class, ClassTableEntry]


def short_name(c: Class) -> Var:
    return c.name.rsplit(".", 1)[-1]


def ancestors(sigma: ClassTable, c: Class) -> list[Class]:
    base = sigma[c].base
    return [c] if base is None else [c] + ancestors(sigma, base)


def fields(sigma: ClassTable, c: Class) -> tuple[Var, ...]:
    entry = sigma[c]
    own = tuple(x for x, _ in entry.own_fields)
    return own if entry.base is None else fields(sigma, entry.base) + own


def field_type(sigma: ClassTable, c: Class, x: Var) -> Type | None:
    entry = sigma[c]
    own = dict(entry.own_fields)
    if x in own:
        return own[x]
    return None if entry.base is None else field_type(sigma, entry.base, x)


def declared_type(sigma: ClassTable, c: Class, x: Var) -> Type:
    t = field_type(sigma, c, x)
    assert t is not None
    return t


def field_map[T](
    sigma: ClassTable,
    c: Class,
    positional: Sequence[T],
    kwd_names: Sequence[str],
    kwd_values: Sequence[T],
) -> dict[Var, T] | None:
    xs = fields(sigma, c)
    n = len(positional)
    if n + len(kwd_names) != len(xs) or len(set(kwd_names)) != len(kwd_names):
        return None
    if set(kwd_names) != set(xs[n:]):
        return None
    return {**dict(zip(xs[:n], positional)), **dict(zip(kwd_names, kwd_values))}
