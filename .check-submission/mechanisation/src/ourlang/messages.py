"""Messages for the reasons of the generated type checker, with names, types, expressions and patterns
unparsed to Python source"""

import ast
from functools import reduce

from .generated import Option, Reasons, Syntax
from .syntax import (
    BOP_AST,
    PRIMITIVE,
    SYMBOL,
    UOP_AST,
    Expr,
    Lit,
    Pat,
    QualifiedName,
    Qualifier,
    Reason,
    Ty,
    node,
)


def unparse_name(q: QualifiedName) -> str:
    x, xs = q
    return ".".join([x, *xs])


def lit_value(ell: Lit) -> bool | int | float | str | None:
    match ell:
        case Syntax.LitInt(v) | Syntax.LitBool(v) | Syntax.LitFloat(v) | Syntax.LitString(v):
            assert isinstance(v, bool | int | float | str)
            return v
        case Syntax.LitNone():
            return None
        case _:
            raise AssertionError(f"unexpected literal: {ell}")


def unparse_type(tau: Ty) -> str:
    match tau:
        case Syntax.TyPrim(nu):
            return PRIMITIVE[type(nu)]
        case Syntax.TyList(sigma):
            return f"list[{unparse_type(sigma)}]"
        case Syntax.TyTuple(taus):
            return f"tuple[{', '.join(unparse_type(c) for c in taus)}]"
        case Syntax.TyDict(sigma):
            return f"dict[str, {unparse_type(sigma)}]"
        case Syntax.TyCallable(sigmas, tau_):
            params = ", ".join(unparse_type(p) for p in sigmas)
            return f"Callable[[{params}], {unparse_type(tau_)}]"
        case Syntax.TyLiteral(ell):
            return f"Literal[{lit_value(ell)!r}]"
        case Syntax.TyVar(alpha):
            return str(alpha)
        case Syntax.TyClass(c, taus):
            args = ", ".join(unparse_type(a) for a in taus)
            return unparse_name(c) if len(taus) == 0 else f"{unparse_name(c)}[{args}]"
        case Syntax.TyUnion(sigma, tau_):
            return f"{unparse_type(sigma)} | {unparse_type(tau_)}"
        case _:
            raise AssertionError(f"unexpected type: {tau}")


def unparse_expr(e: Expr) -> str:
    def ast_expr(e: Expr) -> ast.expr:
        match node(e):
            case Syntax.ExprVar(x):
                return ast.Name(x)
            case Syntax.ExprLiteral(ell):
                return ast.Constant(lit_value(ell))
            case Syntax.ExprCall(f, (es, kws)):
                return ast.Call(
                    ast_expr(f),
                    [ast_expr(e_) for e_ in es],
                    [ast.keyword(x, ast_expr(e_)) for x, e_ in kws],
                )
            case Syntax.ExprDict(kvs):
                return ast.Dict([ast_expr(k) for k, _ in kvs], [ast_expr(v) for _, v in kvs])
            case Syntax.ExprAttribute(e_, x):
                return ast.Attribute(ast_expr(e_), x)
            case Syntax.ExprSubscript(e_, e__):
                return ast.Subscript(ast_expr(e_), ast_expr(e__))
            case Syntax.ExprBinOp(op, e_, e__):
                op_ = BOP_AST[type(op)]
                if issubclass(op_, ast.cmpop):
                    return ast.Compare(ast_expr(e_), [op_()], [ast_expr(e__)])
                return ast.BinOp(ast_expr(e_), op_(), ast_expr(e__))
            case Syntax.ExprUnOp(op, e_):
                return ast.UnaryOp(UOP_AST[type(op)](), ast_expr(e_))
            case Syntax.ExprAnd(e_, e__):
                return ast.BoolOp(ast.And(), [ast_expr(e_), ast_expr(e__)])
            case Syntax.ExprOr(e_, e__):
                return ast.BoolOp(ast.Or(), [ast_expr(e_), ast_expr(e__)])
            case Syntax.ExprCond(e_, e__, e___):
                return ast.IfExp(ast_expr(e__), ast_expr(e_), ast_expr(e___))
            case Syntax.ExprList(es):
                return ast.List([ast_expr(e_) for e_ in es])
            case Syntax.ExprTuple(es):
                return ast.Tuple([ast_expr(e_) for e_ in es])
            case Syntax.ExprListComp(e_, qs):
                return ast.ListComp(ast_expr(e_), ast_comprehensions(qs))
            case Syntax.ExprDictComp(e_, e__, qs):
                return ast.DictComp(ast_expr(e_), ast_expr(e__), ast_comprehensions(qs))
            case Syntax.ExprLambda(xs, e_):
                args = ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(x) for x in xs],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                )
                return ast.Lambda(args, ast_expr(e_))
            case _:
                raise AssertionError(f"unexpected expression: {e}")

    def ast_comprehensions(qs: list[Qualifier]) -> list[ast.comprehension]:
        """Comprehension node per generator in qs, whose conditions are the guards following the generator"""

        def add(gs: list[ast.comprehension], q: Qualifier) -> list[ast.comprehension]:
            match node(q):
                case Syntax.Generator(x, e):
                    return [*gs, ast.comprehension(ast.Name(x), ast_expr(e), [], 0)]
                case Syntax.Guard(e):
                    *gs_, g = gs
                    return [*gs_, ast.comprehension(g.target, g.iter, [*g.ifs, ast_expr(e)], 0)]
                case _:
                    raise AssertionError(f"unexpected qualifier: {q}")

        return reduce(add, qs, [])

    return ast.unparse(ast_expr(e))


SEQUENCE_KIND = {
    Syntax.TupleKind(): "tuple",
    Syntax.ListKind(): "list",
    Syntax.RangeKind(): "range",
}


def unparse_pat(p: Pat) -> str:
    match node(p):
        case Syntax.PatLiteral(ell):
            return ast.unparse(ast.Constant(lit_value(ell)))
        case Syntax.PatVar(x):
            return str(x)
        case Syntax.PatWildcard():
            return "_"
        case Syntax.PatAs(p_, x):
            return f"{unparse_pat(p_)} as {x}"
        case Syntax.PatList(ps):
            return "[" + ", ".join(map(unparse_pat, ps)) + "]"
        case Syntax.PatTuple(ps):
            return "(" + ", ".join(map(unparse_pat, ps)) + ")"
        case Syntax.PatDict(kps):
            items = (f"{ast.unparse(ast.Constant(w))}: {unparse_pat(q)}" for w, q in kps)
            return "{" + ", ".join(items) + "}"
        case Syntax.PatConstr(q, (ps, kps)):
            args = [unparse_pat(p_) for p_ in ps] + [f"{x}={unparse_pat(p_)}" for x, p_ in kps]
            return f"{unparse_name(q)}({', '.join(args)})"
        case _:
            raise AssertionError(f"unexpected pattern: {p}")


def message(r: Reason) -> str:
    match r:
        case Reasons.DuplicateField(x, c):
            return f"duplicate field '{x}' in class '{c}'"
        case Reasons.InheritedField(x, c, d):
            return f"field '{x}' of class '{c}' is also a field of base class '{d}'"
        case Reasons.UndefinedVariable(x):
            return f"'{x}' is not defined"
        case Reasons.UnassignedVariable(x):
            return f"'{x}' is declared but not yet assigned"
        case Reasons.PossiblyUnassigned(x, declared_in_branch):
            qualifier = ": declared in a branch" if declared_in_branch else ""
            return f"'{x}' is not definitely assigned{qualifier}"
        case Reasons.UnboundName(x):
            return f"'{x}' is unbound"
        case Reasons.Redeclaration(x):
            return f"'{x}' is already declared"
        case Reasons.UndeclaredAssignment(x):
            return f"'{x}' is assigned but never declared"
        case Reasons.AssignmentBeforeDeclaration(x):
            return f"'{x}' is assigned before its declaration"
        case Reasons.Reassignment(x):
            return f"'{x}' is already assigned"
        case Reasons.PossibleReassignment(x):
            return f"'{x}' may already be assigned"
        case Reasons.CapturedGeneratorVariable(x):
            return f"'{x}' bound by generator, captured by lambda"
        case Reasons.UnreachableStatement():
            return "unreachable statement"
        case Reasons.ConstructorArityMismatch(c, m, n):
            return f"constructor for '{c}' expects {m} arguments, got {n}"
        case Reasons.UnknownConstructorKeyword(c, xs):
            return f"constructor keywords for '{c}' must be {', '.join(xs)}"
        case Reasons.PatternArityMismatch(c, m, n):
            return f"pattern for '{c}' expects {m} sub-patterns, got {n}"
        case Reasons.UnknownFieldInPattern(c, xs):
            return f"pattern keywords for '{c}' must be {', '.join(xs)}"
        case Reasons.RangePattern():
            return "'range' not permitted in a constructor pattern"
        case Reasons.PatternClassUndetermined(c, tau):
            return f"type arguments of '{c}' in pattern not determined by type {unparse_type(tau)}"
        case Reasons.SequenceKindMismatch(kind, tau, other):
            return f"{SEQUENCE_KIND[kind]} pattern at {unparse_type(tau)}, which has {SEQUENCE_KIND[other]} values"
        case Reasons.UnreachableCase(p):
            return f"case {unparse_pat(p)} is unreachable"
        case Reasons.MissingReturnMatchPartial(tau):
            return f"cases leave remaining type {unparse_type(tau)}, so the function does not always return"
        case Reasons.MissingReturnAssertion():
            return (
                "assertion of expression of type Literal[False] other than False, "
                "so the function does not always return"
            )
        case Reasons.NotPredefinedName(x):
            return f"'{x}' is not bound as a predefined name"
        case Reasons.NotTypeExpression(e):
            return f"'{unparse_expr(e)}' is not a type expression"
        case Reasons.NotClass(q):
            return f"'{unparse_name(q)}' is not a declared class"
        case Reasons.ClassArityMismatch(q, m, n):
            return f"class '{unparse_name(q)}' expects {m} type arguments, given {n}"
        case Reasons.TypeAliasArityMismatch(q, m, n):
            return f"type alias '{unparse_name(q)}' expects {m} type arguments, given {n}"
        case Reasons.CyclicTypeAlias(x):
            return f"type alias '{x}' is cyclic"
        case Reasons.DuplicateMember(x, q):
            return (
                f"duplicate member of module '{unparse_name(q)}': "
                f"it defines '{x}' and also has submodule '{unparse_name(q)}.{x}'"
            )
        case Reasons.SubmoduleNotImported(q):
            return f"submodule '{unparse_name(q)}' is not imported"
        case Reasons.UnassignedMember(x, q):
            return f"member '{x}' of module '{unparse_name(q)}' is not definitely assigned"
        case Reasons.TopLevelAssertFalse():
            return "module body definitely reaches 'assert False'"
        case Reasons.UnknownModule(q):
            return f"unknown module '{unparse_name(q)}'"
        case Reasons.DuplicateImportedName(x):
            return f"name '{x}' imported twice"
        case Reasons.UnknownMember(x, q):
            return f"module '{unparse_name(q)}' has no member '{x}'"
        case Reasons.ModuleAsValue(q):
            return f"'{unparse_name(q)}' refers to a module; modules are not first-class values"
        case Reasons.ImportOfContainedModule(q, q_):
            return (
                f"'{unparse_name(q)}' is contained in importing module '{unparse_name(q_)}'; "
                f"plain import not allowed, write 'from {unparse_name(q)} import <name>'"
            )
        case Reasons.PredefinedNameAsValue(q):
            return f"'{unparse_name(q)}' is usable only in annotations or as a decorator"
        case Reasons.TypeParameterAsValue(x):
            return f"'{x}' is a type parameter, usable only in annotations"
        case Reasons.TypeSchemeAsValue(q):
            return f"type arguments of '{unparse_name(q)}' cannot be inferred"
        case Reasons.NoTypeArgument(alpha):
            return f"type parameter '{alpha}' has no type argument"
        case Reasons.ClassAsValue(q):
            return f"'{unparse_name(q)}' refers to a class; classes are not first-class values"
        case Reasons.TypeAliasAsValue(q):
            return f"'{unparse_name(q)}' is a type alias, usable only in annotations"
        case Reasons.NoBinaryOverload(op, sigma, sigma_):
            return (
                f"no overload of '{SYMBOL[BOP_AST[type(op)]]}' at operand types "
                f"{unparse_type(sigma)} and {unparse_type(sigma_)}"
            )
        case Reasons.NoUnaryOverload(op, sigma):
            return f"no overload of '{SYMBOL[UOP_AST[type(op)]]}' at operand type {unparse_type(sigma)}"
        case Reasons.NotCallable(tau):
            return f"values of type {unparse_type(tau)} cannot be called"
        case Reasons.KeywordArgumentsNotConstructor():
            return "keyword arguments in a call other than a constructor call"
        case Reasons.CallArityMismatch(m, n):
            return f"call expects {m} arguments, given {n}"
        case Reasons.NoneResult():
            return "call returning None used as an expression"
        case Reasons.TypeMismatch(tau, sigma):
            return f"expected type {unparse_type(tau)}, given {unparse_type(sigma)}"
        case Reasons.LambdaTypeMismatch(tau, Option.Some(n)):
            return f"expected type {unparse_type(tau)}, given a lambda of {n} parameter{'' if n == 1 else 's'}"
        case Reasons.LambdaTypeMismatch(tau, Option.None_()):
            return f"expected type {unparse_type(tau)}, given a lambda"
        case Reasons.NotSubscriptable(tau):
            return f"values of type {unparse_type(tau)} cannot be subscripted"
        case Reasons.TupleIndexOutOfRange(i, n):
            return f"index {i} out of range for tuple of length {n}"
        case Reasons.NotIterable(tau):
            return f"values of type {unparse_type(tau)} cannot be iterated"
        case Reasons.NotSynthesised():
            return "cannot infer type of this expression"
        case Reasons.UnknownField(c, x):
            return f"class '{c}' has no field '{x}'"
        case Reasons.NoAttributes(tau):
            return f"values of type {unparse_type(tau)} have no attributes"
        case Reasons.BareReturn(tau):
            return f"bare return in function with result type {unparse_type(tau)}"
        case Reasons.MissingReturn(x, tau):
            return f"'{x}' declares result type {unparse_type(tau)} but does not always return"
        case Reasons.MypyCompatibility(r_):
            return f"{message(r_)} (mypy compatibility)"
        case Reasons.Located(_, r_):
            return message(r_)
        case Reasons.ImportCycle(qs):
            return f"import cycle: {' -> '.join(unparse_name(q) for q in qs)}"
        case _:
            raise AssertionError(f"unexpected reason: {r}")
