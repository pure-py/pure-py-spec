import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto

from type_syntax import Type


class Status(Enum):
    TT = auto()
    FF = auto()


# The entry for a variable is its type where that is known, Status.TT where it is
# assigned but not yet typed, and Status.FF where it is not definitely assigned.
# Lazily evaluated, so these may name ClassEntry before it is defined.
type VarEntry = Status | Type
type ContextEntry = VarEntry | ModuleStub | ModuleLoaded | ClassEntry
type Context = dict[str, ContextEntry]
type VarContext = dict[str, VarEntry]


@dataclass(frozen=True)
class ClassEntry:
    context: Context
    name: str
    own_fields: tuple[str, ...]
    base: str | None


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
    M: dict[str, ast.Module] = field(default_factory=dict)
    q: str = ""


def override_gamma(ctx: ModuleContext, delta: Context) -> ModuleContext:
    return ModuleContext(gamma={**ctx.gamma, **delta}, M=ctx.M, q=ctx.q)


def override_var(ctx: ModuleContext, delta: Mapping[str, VarEntry]) -> ModuleContext:
    return override_gamma(ctx, dict(delta))


def var_entry(ctx: ModuleContext, x: str) -> VarEntry | None:
    v = ctx.gamma.get(x)
    return (
        None
        if v is None or isinstance(v, (ModuleStub, ModuleLoaded, ClassEntry))
        else v
    )


def is_assigned(ctx: ModuleContext, x: str) -> bool:
    v = var_entry(ctx, x)
    return v is not None and v != Status.FF


def class_of(ctx: ModuleContext, c: str) -> ClassEntry | None:
    v = ctx.gamma.get(c)
    return v if isinstance(v, ClassEntry) else None


def module_of(ctx: ModuleContext, x: str) -> ModuleStub | ModuleLoaded | None:
    v = ctx.gamma.get(x)
    return v if isinstance(v, (ModuleStub, ModuleLoaded)) else None


@dataclass(frozen=True)
class Returns:
    pass


@dataclass(frozen=True)
class Assigns:
    delta: VarContext = field(default_factory=dict)


type ResultType = Returns | Assigns

RETURNS = Returns()

ASSIGNS_EMPTY = Assigns()

PREDEFINED_MEMBERS: dict[str, set[str]] = {
    "builtins": {"print", "len", "range"},
    "math": {"pi", "e", "sqrt", "exp", "log", "sin", "cos", "tan", "floor", "ceil"},
    "sys": {"argv", "exit"},
    "typing": {"Any", "Callable"},
    "dataclasses": {"dataclass"},
}

PREDEFINED_MODULES = set(PREDEFINED_MEMBERS)


def predefined_context(q: str) -> Context:
    return {x: Status.TT for x in PREDEFINED_MEMBERS[q] | {"__name__"}}


def merge_entry(a: VarEntry, b: VarEntry) -> VarEntry:
    """Assigned in both branches at the same type gives that type; assigned in
    both at different types is assigned with no type yet."""
    if a == Status.FF or b == Status.FF:
        return Status.FF
    return a if a == b else Status.TT


def merge_delta(d1: VarContext, d2: VarContext) -> VarContext:
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


def fold_merge(acc: VarContext, branches: list[Assigns]) -> VarContext:
    if len(branches) == 0:
        return acc
    return fold_merge(merge_delta(acc, branches[0].delta), branches[1:])


def override_delta(d1: VarContext, d2: VarContext) -> VarContext:
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
    if isinstance(e, ast.Name):
        return ctx.gamma.get(e.id)
    if isinstance(e, ast.Attribute):
        parent = entry_of(e.value, ctx)
        if isinstance(parent, ModuleLoaded):
            return parent.members.get(e.attr)
        return None
    return None


def class_entry(e: ast.expr, ctx: ModuleContext) -> ClassEntry | None:
    entry = entry_of(e, ctx)
    return entry if isinstance(entry, ClassEntry) else None


def short_name(entry: ClassEntry) -> str:
    return entry.name.rsplit(".", 1)[-1]


def ancestors(entry: ClassEntry) -> list[ClassEntry]:
    if entry.base is None:
        return [entry]
    base_entry = entry.context[entry.base]
    assert isinstance(base_entry, ClassEntry)
    return [entry] + ancestors(base_entry)


def fields(entry: ClassEntry) -> tuple[str, ...]:
    if entry.base is None:
        return entry.own_fields
    base_entry = entry.context[entry.base]
    assert isinstance(base_entry, ClassEntry)
    return fields(base_entry) + entry.own_fields


def field_map[T](
    entry: ClassEntry,
    positional: Sequence[T],
    kwd_names: Sequence[str],
    kwd_values: Sequence[T],
) -> dict[str, T] | None:
    xs = fields(entry)
    n = len(positional)
    if n + len(kwd_names) != len(xs) or len(set(kwd_names)) != len(kwd_names):
        return None
    if set(kwd_names) != set(xs[n:]):
        return None
    return {**dict(zip(xs[:n], positional)), **dict(zip(kwd_names, kwd_values))}
