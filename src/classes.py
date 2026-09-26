from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from type_syntax import ClassType, FieldScheme, Name, Type, Var, instantiate


@dataclass(frozen=True)
class Class:
    name: Name

    def __repr__(self) -> str:
        return f"Class({self.name})"


@dataclass(frozen=True)
class ClassTableEntry:
    type_params: tuple[Var, ...]
    own_fields: tuple[tuple[Var, Type], ...]
    base: ClassType | None


type ClassTable = Mapping[Class, ClassTableEntry]


def short_name(c: Class) -> Var:
    return c.name.parts[-1]


def ancestors(Sigma: ClassTable, c: Class) -> list[Class]:
    base = Sigma[c].base
    return [c] if base is None else [c] + ancestors(Sigma, base.c)


def fields(Sigma: ClassTable, c: Class) -> FieldScheme:
    class_entry = Sigma[c]
    if class_entry.base is None:
        return FieldScheme(class_entry.type_params, class_entry.own_fields)
    inherited = instantiate(fields(Sigma, class_entry.base.c), class_entry.base.args)
    return FieldScheme(class_entry.type_params, inherited + class_entry.own_fields)


def field_names(Sigma: ClassTable, c: Class) -> tuple[Var, ...]:
    return tuple(x for x, _ in fields(Sigma, c).fields)


def field_type(Sigma: ClassTable, tau: ClassType, x: Var) -> Type | None:
    return dict(instantiate(fields(Sigma, tau.c), tau.args)).get(x)


def declared_type(Sigma: ClassTable, tau: ClassType, x: Var) -> Type:
    sigma = field_type(Sigma, tau, x)
    assert sigma is not None
    return sigma


def field_map[T](
    Sigma: ClassTable,
    c: Class,
    positional: Sequence[T],
    kwd_names: Sequence[str],
    kwd_values: Sequence[T],
) -> dict[Var, T] | None:
    xs = field_names(Sigma, c)
    n = len(positional)
    if n + len(kwd_names) != len(xs) or len(set(kwd_names)) != len(kwd_names):
        return None
    if set(kwd_names) != set(xs[n:]):
        return None
    return {**dict(zip(xs[:n], positional)), **dict(zip(kwd_names, kwd_values))}


@dataclass(frozen=True)
class ArityMismatch:
    expected: int
    given: int


@dataclass(frozen=True)
class RepeatedKeywordArgument:
    pass


@dataclass(frozen=True)
class UnknownKeywordArguments:
    xs: tuple[Var, ...]


type FieldMapFailure = ArityMismatch | RepeatedKeywordArgument | UnknownKeywordArguments


def no_field_map(Sigma: ClassTable, c: Class, n: int, kwd_names: Sequence[str]) -> FieldMapFailure:
    """Why field-map is undefined for n positional arguments and the keywords kwd_names."""
    xs = field_names(Sigma, c)
    if n + len(kwd_names) != len(xs):
        return ArityMismatch(len(xs), n + len(kwd_names))
    if len(set(kwd_names)) != len(kwd_names):
        return RepeatedKeywordArgument()
    return UnknownKeywordArguments(tuple(sorted(set(xs[n:]))))
