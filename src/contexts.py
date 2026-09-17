import ast
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto

from classes import Class, ClassTable
from subtyping import join_seq
from type_syntax import (
    CallableType,
    ListType,
    Primitive,
    QualifiedName,
    Type,
    Var,
    dotted_name,
    parent,
    parse_qualified,
    root,
)


class Status(Enum):
    FF = auto()


# The entry for a variable is its type, or Status.FF where it is not definitely
# assigned. Lazily evaluated, so these may name Class before it is defined.
type VarEntry = Status | Type
type ContextEntry = VarEntry | ModuleStub | ModuleLoaded | Class | PredefinedName
type Context = Mapping[Var, ContextEntry]
type VarContext = Mapping[Var, VarEntry]


@dataclass(frozen=True)
class PredefinedName:
    pass


@dataclass(frozen=True)
class ModuleStub:
    q: QualifiedName


@dataclass(frozen=True)
class ModuleLoaded:
    q: QualifiedName
    members: Context


@dataclass(frozen=True)
class ModuleContext:
    gamma: Context
    M: Mapping[QualifiedName, ast.Module]
    q: QualifiedName
    Sigma: ClassTable


def override_gamma(mod_ctx: ModuleContext, delta: Context) -> ModuleContext:
    return ModuleContext(
        gamma={**mod_ctx.gamma, **delta}, M=mod_ctx.M, q=mod_ctx.q, Sigma=mod_ctx.Sigma
    )


def var_entry(mod_ctx: ModuleContext, x: Var) -> VarEntry | None:
    theta = mod_ctx.gamma.get(x)
    if theta is None or isinstance(
        theta, (ModuleStub, ModuleLoaded, Class, PredefinedName)
    ):
        return None
    return theta


def assigned_type(mod_ctx: ModuleContext, x: Var) -> Type | None:
    theta = var_entry(mod_ctx, x)
    return None if theta is None or isinstance(theta, Status) else theta


def is_assigned(mod_ctx: ModuleContext, x: Var) -> bool:
    theta = var_entry(mod_ctx, x)
    return theta is not None and theta != Status.FF


def resolve_name(q: QualifiedName, mod_ctx: ModuleContext) -> ContextEntry | None:
    q_ = parent(q)
    if q_ is None:
        return mod_ctx.gamma.get(root(q))
    theta = resolve_name(q_, mod_ctx)
    return theta.members.get(q.parts[-1]) if isinstance(theta, ModuleLoaded) else None


def module_of(mod_ctx: ModuleContext, x: Var) -> ModuleStub | ModuleLoaded | None:
    theta = mod_ctx.gamma.get(x)
    return theta if isinstance(theta, (ModuleStub, ModuleLoaded)) else None


@dataclass(frozen=True)
class Returns:
    pass


@dataclass(frozen=True)
class Assigns:
    delta: Context


type StaticOutcome = Returns | Assigns


FLOAT_TO_FLOAT = CallableType((Primitive.FLOAT,), Primitive.FLOAT)
FLOAT_TO_INT = CallableType((Primitive.FLOAT,), Primitive.INT)

# The type of each predefined member, with PredefinedName for the members
# usable only in an annotation or as a decorator.
PREDEFINED_MEMBERS: dict[str, Context] = {
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

PREDEFINED_MODULES = {parse_qualified(name) for name in PREDEFINED_MEMBERS}
BUILTINS = parse_qualified("builtins")
MAIN = parse_qualified("__main__")


def predefined_context(q: QualifiedName) -> Context:
    return {**PREDEFINED_MEMBERS[str(q)], "__name__": Primitive.STR}


def merge_entry(
    Sigma: ClassTable, theta: ContextEntry, theta_: ContextEntry
) -> VarEntry:
    """Assigned in both branches gives the join of the two types; assigned in
    one alone is not definitely assigned. Only variables are assigned within a
    branch, since a class is declared at the top level alone."""
    assert not isinstance(theta, (ModuleStub, ModuleLoaded, Class, PredefinedName))
    assert not isinstance(theta_, (ModuleStub, ModuleLoaded, Class, PredefinedName))
    if theta == Status.FF or theta_ == Status.FF:
        return Status.FF
    return join_seq(Sigma, [theta, theta_])


def merge_context(Sigma: ClassTable, gamma: Context, gamma_: Context) -> VarContext:
    return {
        x: merge_entry(Sigma, gamma[x], gamma_[x])
        if x in gamma and x in gamma_
        else Status.FF
        for x in set(gamma.keys()) | set(gamma_.keys())
    }


def merge_outcomes(Sigma: ClassTable, rs: list[StaticOutcome]) -> StaticOutcome:
    assigns_branches = [r for r in rs if isinstance(r, Assigns)]
    if len(assigns_branches) == 0:
        return Returns()
    delta = assigns_branches[0].delta
    return Assigns(fold_merge(Sigma, delta, assigns_branches[1:]))


def fold_merge(Sigma: ClassTable, delta: Context, rs: list[Assigns]) -> Context:
    if len(rs) == 0:
        return delta
    return fold_merge(Sigma, merge_context(Sigma, delta, rs[0].delta), rs[1:])


def override_context(gamma: Context, delta: Context) -> Context:
    return {**gamma, **delta}


def override_outcomes(r: StaticOutcome, r_: StaticOutcome) -> StaticOutcome:
    match (r, r_):
        case (Returns(), _):
            return r
        case (_, Returns()):
            return r_
        case (Assigns(delta), Assigns(delta_)):
            return Assigns(override_context(delta, delta_))


def extend_entry(
    theta: ContextEntry | None, theta_: ContextEntry | None
) -> ContextEntry:
    if theta is None:
        assert theta_ is not None
        return theta_
    if theta_ is None:
        return theta
    match (theta, theta_):
        case (ModuleLoaded(q, gamma), ModuleLoaded(q_, gamma_)):
            return ModuleLoaded(q, extend_context(gamma, gamma_)) if q == q_ else theta_
        case (ModuleLoaded(q), ModuleStub(q_)):
            return theta if q == q_ else theta_
        case _:
            return theta_


def disjoint_union[V](
    gamma: Mapping[Var, V], gamma_: Mapping[Var, V]
) -> Mapping[Var, V]:
    assert gamma.keys().isdisjoint(gamma_.keys())
    return {**gamma, **gamma_}


def join_context(Sigma: ClassTable, deltas: list[VarContext]) -> VarContext:
    return {
        x: join_seq(Sigma, binding_types([delta[x] for delta in deltas]))
        for x in deltas[0]
    }


def binding_types(entries: list[VarEntry]) -> list[Type]:
    types = [e for e in entries if not isinstance(e, Status)]
    assert len(types) == len(entries)
    return types


def extend_context(gamma: Context, gamma_: Context) -> Context:
    return {
        x: extend_entry(gamma.get(x), gamma_.get(x))
        for x in list(gamma) + [x for x in gamma_ if x not in gamma]
    }


def entry_of(e: ast.expr, mod_ctx: ModuleContext) -> ContextEntry | None:
    q = dotted_name(e)
    return None if q is None else resolve_name(q, mod_ctx)


def class_of_name(e: ast.expr, mod_ctx: ModuleContext) -> Class | None:
    theta = entry_of(e, mod_ctx)
    return theta if isinstance(theta, Class) else None
