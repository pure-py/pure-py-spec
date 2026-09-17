from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classes import Class


class Primitive(Enum):
    OBJECT = "object"
    NEVER = "Never"
    NONE = "None"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"
    SIZED = "Sized"


type Var = str


@dataclass(frozen=True)
class QualifiedName:
    parts: tuple[Var, ...]

    def __str__(self) -> str:
        return ".".join(self.parts)


def parse_qualified(name: str) -> QualifiedName:
    return QualifiedName(tuple(name.split(".")))


def qualified(q: QualifiedName, x: Var) -> QualifiedName:
    return QualifiedName(q.parts + (x,))


def root(q: QualifiedName) -> Var:
    return q.parts[0]


def parent(q: QualifiedName) -> QualifiedName | None:
    return QualifiedName(q.parts[:-1]) if len(q.parts) > 1 else None


def prefix_of(p: QualifiedName, q: QualifiedName) -> bool:
    return q.parts[: len(p.parts)] == p.parts


def proper_prefix_of(p: QualifiedName, q: QualifiedName) -> bool:
    return p != q and prefix_of(p, q)


def proper_prefixes(q: QualifiedName) -> list[QualifiedName]:
    return [QualifiedName(q.parts[:i]) for i in range(1, len(q.parts))]


@dataclass(frozen=True, eq=False)
class LiteralType:
    """A literal type. Equality compares the value's Python type as well, since
    True == 1 and 1 == 1.0 hold between values of different types."""

    value: object

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, LiteralType)
            and type(self.value) is type(other.value)
            and self.value == other.value
        )

    def __hash__(self) -> int:
        return hash((type(self.value).__name__, self.value))


# Type expressions: types as written, naming a class by a qualified name.


@dataclass(frozen=True)
class ListExpr:
    elem: TypeExpr


@dataclass(frozen=True)
class TupleExpr:
    components: tuple[TypeExpr, ...]


@dataclass(frozen=True)
class DictExpr:
    value: TypeExpr


@dataclass(frozen=True)
class CallableExpr:
    params: tuple[TypeExpr, ...]
    result: TypeExpr


@dataclass(frozen=True)
class ClassName:
    q: QualifiedName


@dataclass(frozen=True)
class UnionExpr:
    left: TypeExpr
    right: TypeExpr


type TypeExpr = (
    Primitive | ListExpr | TupleExpr | DictExpr | CallableExpr | LiteralType | ClassName | UnionExpr
)


# Types: a class type wraps the class entry.


@dataclass(frozen=True)
class ListType:
    elem: Type


@dataclass(frozen=True)
class TupleType:
    components: tuple[Type, ...]


@dataclass(frozen=True)
class DictType:
    value: Type


@dataclass(frozen=True)
class CallableType:
    params: tuple[Type, ...]
    result: Type


@dataclass(frozen=True)
class ClassType:
    c: Class


@dataclass(frozen=True)
class UnionType:
    left: Type
    right: Type


type Type = (
    Primitive | ListType | TupleType | DictType | CallableType | LiteralType | ClassType | UnionType
)


def render(tau: Type) -> str:
    match tau:
        case Primitive():
            return tau.value
        case ListType(sigma):
            return f"list[{render(sigma)}]"
        case TupleType(taus):
            return f"tuple[{', '.join(render(c) for c in taus)}]"
        case DictType(sigma):
            return f"dict[str, {render(sigma)}]"
        case CallableType(sigmas, tau_):
            params = ", ".join(render(p) for p in sigmas)
            return f"Callable[[{params}], {render(tau_)}]"
        case LiteralType():
            return f"Literal[{tau.value!r}]"
        case ClassType(c):
            return str(c.name)
        case UnionType(sigma, tau_):
            return f"{render(sigma)} | {render(tau_)}"


def base_type(v: object) -> Type:
    if isinstance(v, LiteralType):
        return base_type(v.value)
    if isinstance(
        v,
        (
            Primitive,
            ListType,
            TupleType,
            DictType,
            CallableType,
            ClassType,
            UnionType,
        ),
    ):
        return v
    if v is None:
        return Primitive.NONE
    if isinstance(v, bool):
        return Primitive.BOOL
    if isinstance(v, int):
        return Primitive.INT
    if isinstance(v, float):
        return Primitive.FLOAT
    assert isinstance(v, str)
    return Primitive.STR


def parse_annotation(e: ast.expr) -> TypeExpr | None:
    match e:
        case ast.Constant(value=None):
            return Primitive.NONE
        case ast.Name(id=x):
            return next(
                (nu for nu in Primitive if nu.value == x),
                ClassName(QualifiedName((x,))),
            )
        case ast.Attribute():
            q = dotted_name(e)
            return None if q is None else ClassName(q)
        case ast.BinOp(op=ast.BitOr()):
            return union(parse_annotation(e.left), parse_annotation(e.right))
        case ast.Subscript():
            return parse_subscript(e)
        case _:
            return None


def dotted_name(e: ast.expr) -> QualifiedName | None:
    match e:
        case ast.Name(id=x):
            return QualifiedName((x,))
        case ast.Attribute(value=e_, attr=x):
            q = dotted_name(e_)
            return None if q is None else qualified(q, x)
        case _:
            return None


def parse_subscript(e: ast.Subscript) -> TypeExpr | None:
    if not isinstance(e.value, ast.Name):
        return None
    if e.value.id == "Literal":
        return literal_type(e.slice)
    if e.value.id == "Callable":
        return parse_callable(subscript_args(e.slice))
    args = parse_annotations(subscript_args(e.slice))
    if args is None:
        return None
    if e.value.id == "list" and len(args) == 1:
        return ListExpr(args[0])
    if e.value.id == "tuple":
        return TupleExpr(args)
    if e.value.id == "dict" and len(args) == 2 and args[0] == Primitive.STR:
        return DictExpr(args[1])
    return None


def literal_type(e: ast.expr) -> LiteralType | None:
    match e:
        case ast.Constant():
            return LiteralType(e.value)
        case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=n)):
            if isinstance(n, bool) or not isinstance(n, (int, float)):
                return None
            return LiteralType(-n)
        case _:
            return None


def parse_callable(args: tuple[ast.expr, ...]) -> TypeExpr | None:
    if len(args) != 2 or not isinstance(args[0], ast.List):
        return None
    params = parse_annotations(args[0].elts)
    result = parse_annotation(args[1])
    return None if params is None or result is None else CallableExpr(params, result)


def subscript_args(s: ast.expr) -> tuple[ast.expr, ...]:
    return tuple(s.elts) if isinstance(s, ast.Tuple) else (s,)


def parse_annotations(es: Sequence[ast.expr]) -> tuple[TypeExpr, ...] | None:
    psis = tuple(parse_annotation(e) for e in es)
    return (
        None if any(psi is None for psi in psis) else tuple(psi for psi in psis if psi is not None)
    )


def union(psi: TypeExpr | None, psi_: TypeExpr | None) -> TypeExpr | None:
    return None if psi is None or psi_ is None else UnionExpr(psi, psi_)
