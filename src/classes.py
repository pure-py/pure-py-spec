import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import reasons
from aux import TypeDeclaration, own_fields, type_expr, type_param_names
from contexts import (
    BUILTINS,
    Context,
    ModuleContext,
    PredefinedName,
    TypeAlias,
    TypeVar,
    Unbound,
    predefined_context,
    resolve_name,
    type_context,
)
from reasons import IllFormedModule
from type_syntax import (
    RANGE,
    CallableExpr,
    CallableType,
    Class,
    ClassType,
    DictExpr,
    DictType,
    FieldScheme,
    ListExpr,
    ListType,
    LiteralType,
    Name,
    Primitive,
    TupleExpr,
    TupleType,
    Type,
    TypeConstructor,
    TypeExpr,
    TypeName,
    TypeVariable,
    UnionExpr,
    UnionType,
    Var,
    instantiate,
    qualified,
    substitute,
)


@dataclass(frozen=True)
class ClassDef:
    gamma: Context
    q: Name
    xis: tuple[TypeDeclaration, ...]
    i: int


type ClassTable = Mapping[Class, ClassDef]


def short_name(c: Class) -> Var:
    return c.name.parts[-1]


def class_table(gamma: Context, q: Name, xis: tuple[TypeDeclaration, ...], i: int) -> ClassTable:
    xi = xis[i]
    if isinstance(xi, ast.ClassDef):
        return {Class(qualified(q, xi.name)): ClassDef(gamma, q, xis, i)}
    return {}


def class_declaration(Sigma: ClassTable, c: Class) -> ast.ClassDef:
    """Declaration of c, from its definition"""
    definition = Sigma[c]
    xi = definition.xis[definition.i]
    assert isinstance(xi, ast.ClassDef)
    return xi


def definition_context(Sigma: ClassTable, c: Class) -> ModuleContext:
    """Module context resolving type expressions of definition of c: type-context under Sigma.
    Resolution never checks a module, so M is empty."""
    definition = Sigma[c]
    gamma = type_context(definition.gamma, definition.q, definition.xis, definition.i)
    return ModuleContext(gamma=gamma, M={}, q=definition.q, Sigma=Sigma)


def type_params(Sigma: ClassTable, c: Class) -> tuple[Var, ...]:
    return type_param_names(class_declaration(Sigma, c))


def base(Sigma: ClassTable, c: Class) -> ClassType | None:
    xi = class_declaration(Sigma, c)
    if len(xi.bases) == 0:
        return None
    tau = resolve_type(type_expr(xi.bases[0]), xi, definition_context(Sigma, c))
    assert isinstance(tau, ClassType)
    return tau


def ancestors(Sigma: ClassTable, c: Class) -> list[Class]:
    base_ = base(Sigma, c)
    return [c] if base_ is None else [c] + ancestors(Sigma, base_.c)


def fields(Sigma: ClassTable, c: Class) -> FieldScheme:
    xi = class_declaration(Sigma, c)
    own = tuple(
        (x, resolve_type(psi, xi, definition_context(Sigma, c))) for x, psi in own_fields(xi)
    )
    base_ = base(Sigma, c)
    if base_ is None:
        return FieldScheme(type_params(Sigma, c), own)
    inherited = instantiate(fields(Sigma, base_.c), base_.args)
    return FieldScheme(type_params(Sigma, c), inherited + own)


_resolving: list[tuple[Name, Var]] = []


def resolve_type(psi: TypeExpr, node: ast.AST, mod_ctx: ModuleContext) -> Type:
    match psi:
        case Primitive():
            check_in_scope(psi.value, node, mod_ctx)
            return psi
        case LiteralType():
            check_in_scope(TypeConstructor.LITERAL.value, node, mod_ctx)
            return psi
        case TypeName(q, args):
            theta = resolve_name(q, mod_ctx)
            if isinstance(theta, Unbound):
                raise IllFormedModule(node, reasons.UnboundName(str(q)))
            if isinstance(theta, TypeVar) and len(args) == 0:
                return TypeVariable(str(q))
            if isinstance(theta, TypeAlias):
                xi = theta.xis[theta.i]
                assert isinstance(xi, ast.TypeAlias) and isinstance(xi.name, ast.Name)
                alphas = type_param_names(xi)
                sigmas = tuple(resolve_type(psi_, node, mod_ctx) for psi_ in args)
                if len(sigmas) != len(alphas):
                    raise IllFormedModule(
                        node, reasons.TypeAliasArityMismatch(q, len(alphas), len(sigmas))
                    )
                mod_ctx_ = ModuleContext(
                    gamma=type_context(theta.gamma, theta.q, theta.xis, theta.i),
                    M=mod_ctx.M,
                    q=theta.q,
                    Sigma=mod_ctx.Sigma,
                )
                key = (theta.q, xi.name.id)
                if key in _resolving:
                    raise IllFormedModule(node, reasons.CyclicTypeAlias(xi.name.id))
                _resolving.append(key)
                try:
                    tau = resolve_type(type_expr(xi.value), node, mod_ctx_)
                finally:
                    _resolving.pop()
                return substitute(sigmas, alphas, tau)
            if not isinstance(theta, Class):
                raise IllFormedModule(node, reasons.NotClass(q))
            taus = tuple(resolve_type(psi_, node, mod_ctx) for psi_ in args)
            expected = len(type_params(mod_ctx.Sigma, theta))
            if len(taus) != expected:
                raise IllFormedModule(node, reasons.ClassArityMismatch(q, expected, len(taus)))
            return ClassType(theta, taus)
        case ListExpr(psi_):
            check_in_scope(TypeConstructor.LIST.value, node, mod_ctx)
            return ListType(resolve_type(psi_, node, mod_ctx))
        case DictExpr(psi_):
            check_in_scope(TypeConstructor.DICT.value, node, mod_ctx)
            check_in_scope(Primitive.STR.value, node, mod_ctx)
            return DictType(resolve_type(psi_, node, mod_ctx))
        case TupleExpr(psis):
            check_in_scope(TypeConstructor.TUPLE.value, node, mod_ctx)
            return TupleType(tuple(resolve_type(c, node, mod_ctx) for c in psis))
        case CallableExpr(psis, psi_):
            check_in_scope(TypeConstructor.CALLABLE.value, node, mod_ctx)
            return CallableType(
                tuple(resolve_type(p, node, mod_ctx) for p in psis),
                resolve_type(psi_, node, mod_ctx),
            )
        case UnionExpr():
            return UnionType(
                resolve_type(psi.left, node, mod_ctx),
                resolve_type(psi.right, node, mod_ctx),
            )


def check_in_scope(x: Var, node: ast.AST, mod_ctx: ModuleContext) -> None:
    if not isinstance(mod_ctx.gamma.get(x), PredefinedName):
        raise IllFormedModule(node, reasons.NotPredefinedName(x))


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
class RepeatedKeywordArg:
    pass


@dataclass(frozen=True)
class UnknownKeywordArgs:
    xs: tuple[Var, ...]


type FieldMapFailure = ArityMismatch | RepeatedKeywordArg | UnknownKeywordArgs


def no_field_map(Sigma: ClassTable, c: Class, n: int, kwd_names: Sequence[str]) -> FieldMapFailure:
    """Why field-map is undefined for n positional arguments and the keywords kwd_names."""
    xs = field_names(Sigma, c)
    if n + len(kwd_names) != len(xs):
        return ArityMismatch(len(xs), n + len(kwd_names))
    if len(set(kwd_names)) != len(kwd_names):
        return RepeatedKeywordArg()
    return UnknownKeywordArgs(tuple(sorted(set(xs[n:]))))


RANGE_DECLARATION = ast.parse("@dataclass\nclass range:\n    stop: int\n").body[0]
assert isinstance(RANGE_DECLARATION, ast.ClassDef)

PREDEFINED_CLASSES: ClassTable = {
    RANGE: ClassDef(predefined_context(BUILTINS), BUILTINS, (RANGE_DECLARATION,), 0)
}
