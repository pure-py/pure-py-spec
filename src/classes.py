import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import reasons
from aux import TypeDefinition, own_fields, type_expr, type_param_names
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
    ClassName,
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
    chis: tuple[TypeDefinition, ...]
    i: int


type ClassTable = Mapping[ClassName, ClassDef]


def short_name(c: ClassName) -> Var:
    return c.name.parts[-1]


def class_table(gamma: Context, q: Name, chis: tuple[TypeDefinition, ...], i: int) -> ClassTable:
    match chis[i]:
        case ast.ClassDef(name=c):
            return {ClassName(qualified(q, c)): ClassDef(gamma, q, chis, i)}
        case _:
            return {}


def class_definition(Sigma: ClassTable, c: ClassName) -> ast.ClassDef:
    """Class definition of c"""
    match Sigma[c]:
        case ClassDef(chis=chis, i=i):
            chi = chis[i]
            assert isinstance(chi, ast.ClassDef)
            return chi


def definition_context(Sigma: ClassTable, c: ClassName) -> ModuleContext:
    """Module context for resolving annotations of class c; empty module map, because type
    resolution doesn't check modules"""
    match Sigma[c]:
        case ClassDef(gamma, q, chis, i):
            return ModuleContext(gamma=type_context(gamma, q, chis, i), M={}, q=q, Sigma=Sigma)


def type_params(Sigma: ClassTable, c: ClassName) -> tuple[Var, ...]:
    return type_param_names(class_definition(Sigma, c))


def base(Sigma: ClassTable, c: ClassName) -> ClassType | None:
    chi = class_definition(Sigma, c)
    if len(chi.bases) == 0:
        return None
    tau = resolve_type(type_expr(chi.bases[0]), chi, definition_context(Sigma, c))
    assert isinstance(tau, ClassType)
    return tau


def ancestors(Sigma: ClassTable, c: ClassName) -> list[ClassName]:
    base_ = base(Sigma, c)
    return [c] if base_ is None else [c] + ancestors(Sigma, base_.c)


def fields(Sigma: ClassTable, c: ClassName) -> FieldScheme:
    chi = class_definition(Sigma, c)
    own = tuple(
        (x, resolve_type(psi, chi, definition_context(Sigma, c))) for x, psi in own_fields(chi)
    )
    base_ = base(Sigma, c)
    if base_ is None:
        return FieldScheme(type_params(Sigma, c), own)
    inherited = instantiate(fields(Sigma, base_.c), base_.args)
    return FieldScheme(type_params(Sigma, c), inherited + own)


type Resolving = frozenset[tuple[Name, Var]]


def resolve_type(
    psi: TypeExpr, node: ast.AST, mod_ctx: ModuleContext, resolving: Resolving = frozenset()
) -> Type:
    """resolving: aliases whose bodies are being resolved, to reject a cyclic alias"""

    def resolve(psi_: TypeExpr) -> Type:
        return resolve_type(psi_, node, mod_ctx, resolving)

    match psi:
        case Primitive():
            check_in_scope(psi.value, node, mod_ctx)
            return psi
        case LiteralType():
            check_in_scope(TypeConstructor.LITERAL.value, node, mod_ctx)
            return psi
        case TypeName(q, args):
            match resolve_name(q, mod_ctx):
                case Unbound():
                    raise IllFormedModule(node, reasons.UnboundName(str(q)))
                case TypeVar() if len(args) == 0:
                    return TypeVariable(str(q))
                case TypeAlias() as theta:
                    return ty_alias(theta, q, tuple(map(resolve, args)), node, mod_ctx, resolving)
                case ClassName() as c:
                    return ty_class(c, q, tuple(map(resolve, args)), node, mod_ctx)
                case _:
                    raise IllFormedModule(node, reasons.NotClass(q))
        case ListExpr(psi_):
            check_in_scope(TypeConstructor.LIST.value, node, mod_ctx)
            return ListType(resolve(psi_))
        case DictExpr(psi_):
            check_in_scope(TypeConstructor.DICT.value, node, mod_ctx)
            check_in_scope(Primitive.STR.value, node, mod_ctx)
            return DictType(resolve(psi_))
        case TupleExpr(psis):
            check_in_scope(TypeConstructor.TUPLE.value, node, mod_ctx)
            return TupleType(tuple(map(resolve, psis)))
        case CallableExpr(psis, psi_):
            check_in_scope(TypeConstructor.CALLABLE.value, node, mod_ctx)
            return CallableType(tuple(map(resolve, psis)), resolve(psi_))
        case UnionExpr():
            return UnionType(resolve(psi.left), resolve(psi.right))


def ty_alias(
    theta: TypeAlias,
    q: Name,
    sigmas: tuple[Type, ...],
    node: ast.AST,
    mod_ctx: ModuleContext,
    resolving: Resolving,
) -> Type:
    chi = theta.chis[theta.i]
    assert isinstance(chi, ast.TypeAlias) and isinstance(chi.name, ast.Name)
    alphas = type_param_names(chi)
    if len(sigmas) != len(alphas):
        raise IllFormedModule(node, reasons.TypeAliasArityMismatch(q, len(alphas), len(sigmas)))
    alias = (theta.q, chi.name.id)
    if alias in resolving:
        raise IllFormedModule(node, reasons.CyclicTypeAlias(chi.name.id))
    mod_ctx_ = ModuleContext(
        gamma=type_context(theta.gamma, theta.q, theta.chis, theta.i),
        M=mod_ctx.M,
        q=theta.q,
        Sigma=mod_ctx.Sigma,
    )
    tau = resolve_type(type_expr(chi.value), node, mod_ctx_, resolving | {alias})
    return substitute(sigmas, alphas, tau)


def ty_class(
    c: ClassName, q: Name, taus: tuple[Type, ...], node: ast.AST, mod_ctx: ModuleContext
) -> Type:
    expected = len(type_params(mod_ctx.Sigma, c))
    if len(taus) != expected:
        raise IllFormedModule(node, reasons.ClassArityMismatch(q, expected, len(taus)))
    return ClassType(c, taus)


def check_in_scope(x: Var, node: ast.AST, mod_ctx: ModuleContext) -> None:
    if not isinstance(mod_ctx.gamma.get(x), PredefinedName):
        raise IllFormedModule(node, reasons.NotPredefinedName(x))


def field_names(Sigma: ClassTable, c: ClassName) -> tuple[Var, ...]:
    return tuple(x for x, _ in fields(Sigma, c).fields)


def field_type(Sigma: ClassTable, tau: ClassType, x: Var) -> Type | None:
    return dict(instantiate(fields(Sigma, tau.c), tau.args)).get(x)


def declared_type(Sigma: ClassTable, tau: ClassType, x: Var) -> Type:
    sigma = field_type(Sigma, tau, x)
    assert sigma is not None
    return sigma


def field_map[T](
    Sigma: ClassTable,
    c: ClassName,
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


def no_field_map(
    Sigma: ClassTable, c: ClassName, n: int, kwd_names: Sequence[str]
) -> FieldMapFailure:
    """Why field-map is undefined for n positional arguments and the keywords kwd_names."""
    xs = field_names(Sigma, c)
    if n + len(kwd_names) != len(xs):
        return ArityMismatch(len(xs), n + len(kwd_names))
    if len(set(kwd_names)) != len(kwd_names):
        return RepeatedKeywordArg()
    return UnknownKeywordArgs(tuple(sorted(set(xs[n:]))))


RANGE_DECLARATION = ast.parse("@dataclass\nclass range:\n    start: int\n    stop: int\n").body[0]
assert isinstance(RANGE_DECLARATION, ast.ClassDef)

PREDEFINED_CLASSES: ClassTable = {
    RANGE: ClassDef(predefined_context(BUILTINS), BUILTINS, (RANGE_DECLARATION,), 0)
}
