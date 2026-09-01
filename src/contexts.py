import ast
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, auto

from classes import Class
from subtyping import join
from type_syntax import CallableType, ListType, Primitive, Type, dotted_name


class Status(Enum):
    FF = auto()


# The entry for a variable is its type, or Status.FF where it is not definitely
# assigned. Lazily evaluated, so these may name Class before it is defined.
type VarEntry = Status | Type
type ContextEntry = VarEntry | ModuleStub | ModuleLoaded | Class | PredefinedName
type Context = dict[str, ContextEntry]
type VarContext = dict[str, VarEntry]


@dataclass(frozen=True)
class PredefinedName:
    """Name usable only in an annotation or as a decorator: it names a type,
    heads a type form, or decorates a class declaration."""


@dataclass(frozen=True)
class ModuleStub:
    q: str


@dataclass(frozen=True)
class ModuleLoaded:
    q: str
    members: Context


@dataclass(frozen=True)
class ModuleContext:
    gamma: Context
    M: Mapping[str, ast.Module] = field(default_factory=dict)
    q: str = ""


def override_gamma(ctx: ModuleContext, delta: Context) -> ModuleContext:
    return ModuleContext(gamma={**ctx.gamma, **delta}, M=ctx.M, q=ctx.q)


def override_var(ctx: ModuleContext, delta: Mapping[str, VarEntry]) -> ModuleContext:
    return override_gamma(ctx, dict(delta))


def var_entry(ctx: ModuleContext, x: str) -> VarEntry | None:
    v = ctx.gamma.get(x)
    return (
        None
        if v is None or isinstance(v, (ModuleStub, ModuleLoaded, Class, PredefinedName))
        else v
    )


def var_type(ctx: ModuleContext, x: str) -> Type | None:
    """The variable's type, where the context has one for it."""
    v = var_entry(ctx, x)
    return None if v is None or isinstance(v, Status) else v


def is_assigned(ctx: ModuleContext, x: str) -> bool:
    v = var_entry(ctx, x)
    return v is not None and v != Status.FF


def resolve_name(q: str, ctx: ModuleContext) -> ContextEntry | None:
    """Entry a qualified name denotes: its first component in the context, and
    each later one a member of the module the components before it denote."""
    x, *rest = q.split(".")
    entry = ctx.gamma.get(x)
    for y in rest:
        if not isinstance(entry, ModuleLoaded):
            return None
        entry = entry.members.get(y)
    return entry


def module_of(ctx: ModuleContext, x: str) -> ModuleStub | ModuleLoaded | None:
    v = ctx.gamma.get(x)
    return v if isinstance(v, (ModuleStub, ModuleLoaded)) else None


@dataclass(frozen=True)
class Returns:
    pass


@dataclass(frozen=True)
class Assigns:
    delta: Mapping[str, ContextEntry] = field(default_factory=dict)


type ResultType = Returns | Assigns

RETURNS = Returns()

ASSIGNS_EMPTY = Assigns()

FLOAT_TO_FLOAT = CallableType((Primitive.FLOAT,), Primitive.FLOAT)
FLOAT_TO_INT = CallableType((Primitive.FLOAT,), Primitive.INT)

# The type of each predefined member, with PredefinedName for the members
# usable only in an annotation or as a decorator.
PREDEFINED_MEMBERS: dict[str, dict[str, ContextEntry]] = {
    "builtins": {
        "print": CallableType((Primitive.OBJECT,), Primitive.NONE),
        "len": CallableType((Primitive.SIZED,), Primitive.INT),
        "None": PredefinedName(),
        "object": PredefinedName(),
        "bool": PredefinedName(),
        "int": PredefinedName(),
        "float": PredefinedName(),
        "str": PredefinedName(),
        "list": PredefinedName(),
        "dict": PredefinedName(),
        "tuple": PredefinedName(),
    },
    "math": {
        "pi": Primitive.FLOAT,
        "e": Primitive.FLOAT,
        "sqrt": FLOAT_TO_FLOAT,
        "exp": FLOAT_TO_FLOAT,
        "log": FLOAT_TO_FLOAT,
        "sin": FLOAT_TO_FLOAT,
        "cos": FLOAT_TO_FLOAT,
        "tan": FLOAT_TO_FLOAT,
        "floor": FLOAT_TO_INT,
        "ceil": FLOAT_TO_INT,
    },
    "sys": {
        "argv": ListType(Primitive.STR),
        "exit": CallableType((Primitive.INT,), Primitive.NEVER),
    },
    "typing": {
        "Callable": PredefinedName(),
        "Literal": PredefinedName(),
        "Never": PredefinedName(),
        "Sized": PredefinedName(),
    },
    "dataclasses": {"dataclass": PredefinedName()},
}

PREDEFINED_MODULES = set(PREDEFINED_MEMBERS)


def predefined_context(q: str) -> Context:
    return {**PREDEFINED_MEMBERS[q], "__name__": Primitive.STR}


def merge_entry(a: ContextEntry, b: ContextEntry) -> VarEntry:
    """Assigned in both branches gives the join of the two types; assigned in
    one alone is not definitely assigned. Only variables are assigned within a
    branch, since a class is declared at the top level alone."""
    assert not isinstance(a, (ModuleStub, ModuleLoaded, Class, PredefinedName))
    assert not isinstance(b, (ModuleStub, ModuleLoaded, Class, PredefinedName))
    if a == Status.FF or b == Status.FF:
        return Status.FF
    return join([a, b])


def merge_delta(
    d1: Mapping[str, ContextEntry], d2: Mapping[str, ContextEntry]
) -> VarContext:
    return {
        k: merge_entry(d1[k], d2[k]) if k in d1 and k in d2 else Status.FF
        for k in set(d1.keys()) | set(d2.keys())
    }


def merge_results(rs: list[ResultType]) -> ResultType:
    assigns_branches = [r for r in rs if isinstance(r, Assigns)]
    if len(assigns_branches) == 0:
        return RETURNS
    delta = assigns_branches[0].delta
    return Assigns(fold_merge(delta, assigns_branches[1:]))


def fold_merge(
    acc: Mapping[str, ContextEntry], branches: list[Assigns]
) -> Mapping[str, ContextEntry]:
    if len(branches) == 0:
        return acc
    return fold_merge(merge_delta(acc, branches[0].delta), branches[1:])


def override_delta(
    d1: Mapping[str, ContextEntry], d2: Mapping[str, ContextEntry]
) -> Context:
    return {**d1, **d2}


def override_results(r1: ResultType, r2: ResultType) -> ResultType:
    if isinstance(r1, Returns):
        return r1
    if isinstance(r2, Returns):
        return r2
    return Assigns(override_delta(r1.delta, r2.delta))


def extend_entry(a: ContextEntry, b: ContextEntry) -> ContextEntry:
    if isinstance(a, ModuleLoaded) and isinstance(b, ModuleLoaded) and a.q == b.q:
        return ModuleLoaded(a.q, extend_context(a.members, b.members))
    if isinstance(a, ModuleLoaded) and isinstance(b, ModuleStub) and a.q == b.q:
        return a
    return b


def extend_context(g1: Context, g2: Context) -> Context:
    return {
        **g1,
        **{x: extend_entry(g1[x], e) if x in g1 else e for x, e in g2.items()},
    }


def entry_of(e: ast.expr, ctx: ModuleContext) -> ContextEntry | None:
    q = dotted_name(e)
    return None if q is None else resolve_name(q, ctx)


def class_of_name(e: ast.expr, ctx: ModuleContext) -> Class | None:
    entry = entry_of(e, ctx)
    return entry if isinstance(entry, Class) else None
