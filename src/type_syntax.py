import ast
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from contexts import ModuleContext, ancestors, class_of, short_name


class Primitive(Enum):
    ANY = auto()
    OBJECT = auto()
    NEVER = auto()
    NONE = auto()
    BOOL = auto()
    INT = auto()
    FLOAT = auto()
    STR = auto()


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
class LiteralType:
    value: object


@dataclass(frozen=True)
class ClassType:
    q: str


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

PRIMITIVE_NAMES = {
    "Any": Primitive.ANY,
    "object": Primitive.OBJECT,
    "Never": Primitive.NEVER,
    "None": Primitive.NONE,
    "bool": Primitive.BOOL,
    "int": Primitive.INT,
    "float": Primitive.FLOAT,
    "str": Primitive.STR,
}


def base_type(v: object) -> Type:
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


def parse_annotation(e: ast.expr) -> Type | None:
    if isinstance(e, ast.Constant) and e.value is None:
        return Primitive.NONE
    if isinstance(e, ast.Name):
        return PRIMITIVE_NAMES.get(e.id, ClassType(e.id))
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.BitOr):
        return union(parse_annotation(e.left), parse_annotation(e.right))
    if isinstance(e, ast.Subscript):
        return parse_subscript(e)
    return None


def parse_subscript(e: ast.Subscript) -> Type | None:
    if not isinstance(e.value, ast.Name):
        return None
    if e.value.id == "Literal":
        return parse_literal(e.slice)
    if e.value.id == "Callable":
        return parse_callable(subscript_args(e.slice))
    args = parse_annotations(subscript_args(e.slice))
    if args is None:
        return None
    if e.value.id == "list" and len(args) == 1:
        return ListType(args[0])
    if e.value.id == "tuple":
        return TupleType(args)
    if e.value.id == "dict" and len(args) == 2 and args[0] == Primitive.STR:
        return DictType(args[1])
    return None


def parse_literal(s: ast.expr) -> Type | None:
    if isinstance(s, ast.Constant):
        return LiteralType(s.value)
    if isinstance(s, ast.UnaryOp) and isinstance(s.op, ast.USub):
        operand = s.operand
        if isinstance(operand, ast.Constant) and isinstance(
            operand.value, (int, float)
        ):
            return LiteralType(-operand.value)
    return None


def parse_callable(args: tuple[ast.expr, ...]) -> Type | None:
    if len(args) != 2 or not isinstance(args[0], ast.List):
        return None
    params = parse_annotations(args[0].elts)
    result = parse_annotation(args[1])
    return None if params is None or result is None else CallableType(params, result)


def subscript_args(s: ast.expr) -> tuple[ast.expr, ...]:
    return tuple(s.elts) if isinstance(s, ast.Tuple) else (s,)


def parse_annotations(es: Sequence[ast.expr]) -> tuple[Type, ...] | None:
    ts = tuple(parse_annotation(e) for e in es)
    return None if any(t is None for t in ts) else tuple(t for t in ts if t is not None)


def union(s: Type | None, t: Type | None) -> Type | None:
    return None if s is None or t is None else UnionType(s, t)


def alts(t: Type) -> tuple[Type, ...]:
    """The alternatives of a type: a union's operands, or the type itself."""
    if isinstance(t, UnionType):
        return alts(t.left) + alts(t.right)
    return (t,)


def join_two(s: Type, t: Type, ctx: ModuleContext) -> Type:
    if subtype(s, t, ctx):
        return t
    if subtype(t, s, ctx):
        return s
    return UnionType(s, t)


def join(ts: Sequence[Type], ctx: ModuleContext) -> Type:
    assert len(ts) > 0
    if len(ts) == 1:
        return ts[0]
    return join_two(ts[0], join(ts[1:], ctx), ctx)


def subtype(s: Type, t: Type, ctx: ModuleContext) -> bool:
    if s == t or s == Primitive.NEVER or t == Primitive.OBJECT:
        return True
    if s == Primitive.INT and t == Primitive.FLOAT:
        return True
    if isinstance(s, LiteralType):
        return subtype(base_type(s.value), t, ctx)
    if isinstance(s, UnionType):
        return all(subtype(m, t, ctx) for m in alts(s))
    if isinstance(t, UnionType):
        return any(subtype(s, m, ctx) for m in alts(t))
    if isinstance(s, ClassType) and isinstance(t, ClassType):
        return t.q in ancestor_names(s.q, ctx)
    return False


def ancestor_names(q: str, ctx: ModuleContext) -> tuple[str, ...]:
    entry = class_of(ctx, q.rsplit(".", 1)[-1])
    return () if entry is None else tuple(short_name(a) for a in ancestors(entry))


def comparable(s: Type, t: Type, ctx: ModuleContext) -> bool:
    return subtype(s, t, ctx) or subtype(t, s, ctx)


def elem_type(t: Type) -> Type | None:
    if isinstance(t, ListType):
        return t.elem
    if t == Primitive.STR:
        return Primitive.STR
    if isinstance(t, DictType):
        return Primitive.STR
    if isinstance(t, TupleType) and len(set(t.components)) == 1:
        return t.components[0]
    return None
