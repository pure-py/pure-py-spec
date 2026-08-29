import ast
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto


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

PRIMITIVE_SPELLINGS = {
    Primitive.ANY: "Any",
    Primitive.OBJECT: "object",
    Primitive.NEVER: "Never",
    Primitive.NONE: "None",
    Primitive.BOOL: "bool",
    Primitive.INT: "int",
    Primitive.FLOAT: "float",
    Primitive.STR: "str",
}

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


def render(t: Type) -> str:
    """The type as it is written in an annotation."""
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
        return t.q
    return f"{render(t.left)} | {render(t.right)}"


def base_type(v: object) -> Type:
    """The base type of a literal, or of a type: a literal type at the base type
    of its literal, and any other type unchanged."""
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

