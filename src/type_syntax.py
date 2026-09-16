import ast
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classes import Class


class Primitive(Enum):
    OBJECT = auto()
    NEVER = auto()
    NONE = auto()
    BOOL = auto()
    INT = auto()
    FLOAT = auto()
    STR = auto()
    SIZED = auto()


# Variables, the spec's x; fields and class names (c) are variables too.
type Var = str


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
    elem: "TypeExpr"


@dataclass(frozen=True)
class TupleExpr:
    components: tuple["TypeExpr", ...]


@dataclass(frozen=True)
class DictExpr:
    value: "TypeExpr"


@dataclass(frozen=True)
class CallableExpr:
    params: tuple["TypeExpr", ...]
    result: "TypeExpr"


@dataclass(frozen=True)
class ClassName:
    q: str


@dataclass(frozen=True)
class UnionExpr:
    left: "TypeExpr"
    right: "TypeExpr"


type TypeExpr = (
    Primitive
    | ListExpr
    | TupleExpr
    | DictExpr
    | CallableExpr
    | LiteralType
    | ClassName
    | UnionExpr
)


# Types: a class type wraps the class entry.


@dataclass(frozen=True)
class ListType:
    elem: "Type"


@dataclass(frozen=True)
class TupleType:
    components: tuple["Type", ...]


@dataclass(frozen=True)
class DictType:
    value: "Type"


@dataclass(frozen=True)
class CallableType:
    params: tuple["Type", ...]
    result: "Type"


@dataclass(frozen=True)
class ClassType:
    c: "Class"


@dataclass(frozen=True)
class UnionType:
    left: "Type"
    right: "Type"


type Type = (
    Primitive
    | ListType
    | TupleType
    | DictType
    | CallableType
    | LiteralType
    | ClassType
    | UnionType
)

PRIMITIVE_SPELLINGS = {
    Primitive.OBJECT: "object",
    Primitive.NEVER: "Never",
    Primitive.NONE: "None",
    Primitive.BOOL: "bool",
    Primitive.INT: "int",
    Primitive.FLOAT: "float",
    Primitive.STR: "str",
    Primitive.SIZED: "Sized",
}

PRIMITIVE_NAMES = {name: t for t, name in PRIMITIVE_SPELLINGS.items()}


def render(t: Type) -> str:
    if isinstance(t, Primitive):
        return PRIMITIVE_SPELLINGS[t]
    if isinstance(t, ListType):
        return f"list[{render(t.elem)}]"
    if isinstance(t, TupleType):
        return f"tuple[{', '.join(render(c) for c in t.components)}]"
    if isinstance(t, DictType):
        return f"dict[str, {render(t.value)}]"
    if isinstance(t, CallableType):
        params = ", ".join(render(p) for p in t.params)
        return f"Callable[[{params}], {render(t.result)}]"
    if isinstance(t, LiteralType):
        return f"Literal[{t.value!r}]"
    if isinstance(t, ClassType):
        return t.c.name
    return f"{render(t.left)} | {render(t.right)}"


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
    if isinstance(e, ast.Constant) and e.value is None:
        return Primitive.NONE
    if isinstance(e, ast.Name):
        return PRIMITIVE_NAMES.get(e.id, ClassName(e.id))
    if isinstance(e, ast.Attribute):
        q = dotted_name(e)
        return None if q is None else ClassName(q)
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.BitOr):
        return union(parse_annotation(e.left), parse_annotation(e.right))
    if isinstance(e, ast.Subscript):
        return parse_subscript(e)
    return None


def dotted_name(e: ast.expr) -> str | None:
    if isinstance(e, ast.Name):
        return e.id
    if isinstance(e, ast.Attribute):
        q = dotted_name(e.value)
        return None if q is None else f"{q}.{e.attr}"
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
    if isinstance(e, ast.Constant):
        return LiteralType(e.value)
    if not (isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub)):
        return None
    if not isinstance(e.operand, ast.Constant):
        return None
    n = e.operand.value
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        return None
    return LiteralType(-n)


def parse_callable(args: tuple[ast.expr, ...]) -> TypeExpr | None:
    if len(args) != 2 or not isinstance(args[0], ast.List):
        return None
    params = parse_annotations(args[0].elts)
    result = parse_annotation(args[1])
    return None if params is None or result is None else CallableExpr(params, result)


def subscript_args(s: ast.expr) -> tuple[ast.expr, ...]:
    return tuple(s.elts) if isinstance(s, ast.Tuple) else (s,)


def parse_annotations(es: Sequence[ast.expr]) -> tuple[TypeExpr, ...] | None:
    ts = tuple(parse_annotation(e) for e in es)
    return None if any(t is None for t in ts) else tuple(t for t in ts if t is not None)


def union(s: TypeExpr | None, t: TypeExpr | None) -> TypeExpr | None:
    return None if s is None or t is None else UnionExpr(s, t)
