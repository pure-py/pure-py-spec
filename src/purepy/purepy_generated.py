"""Type check a program with the code generated from isabelle-purepy, which must be on PYTHONPATH.
The parsed modules are first translated into the Python types generated from the Isabelle AST
definitions."""

import argparse
import ast
import pathlib
import sys
from functools import reduce
from typing import Any

import Finite_Map
import Option
import Programs
import Reasons
import Syntax

from . import reasons, syntax
from .check_module import containing, name_declaration
from .check_program import error_path, format_program_result, module_names, module_path, parse
from .conformance import Exit
from .contexts import MAIN
from .operators import BINARY_NAMES, UNARY_NAMES
from .reasons import IllFormed, IllFormedModule, IllFormedProgram, MypyCompatibility
from .syntax_utils import (
    Statement,
    dict_keys,
    own_fields,
    split_imports,
    statements,
    target_name,
    type_expr,
    type_param_names,
)
from .type_syntax import (
    CallableExpr,
    CallableType,
    ClassName,
    ClassType,
    DictExpr,
    DictType,
    ListExpr,
    ListType,
    Literal,
    LiteralType,
    Name,
    Primitive,
    TupleExpr,
    TupleType,
    Type,
    TypeExpr,
    TypeName,
    TypeVariable,
    UnionExpr,
    UnionType,
    dotted_name,
    parse_name,
    proper_prefixes,
    qualified,
)


def lit(v: object) -> Any:
    match v:
        case bool():
            return Syntax.LitBool(v)
        case int():
            return Syntax.LitInt(v)
        case float():
            return Syntax.LitFloat(v)
        case str():
            return Syntax.LitString(v)
        case None:
            return Syntax.LitNone()
        case _:
            raise AssertionError(f"unexpected literal: {type(v).__name__}")


def name(q: Name) -> Any:
    return (q.parts[0], list(q.parts[1:]))


def option(x: Any) -> Any:
    return Option.None_() if x is None else Option.Some(x)


PRIM_TY = {
    Primitive.OBJECT: Syntax.object_,
    Primitive.NEVER: Syntax.Never,
    Primitive.NONE: Syntax.NoneType,
    Primitive.BOOL: Syntax.bool_,
    Primitive.INT: Syntax.int_,
    Primitive.FLOAT: Syntax.float_,
    Primitive.STR: Syntax.str_,
    Primitive.SIZED: Syntax.Sized,
}


def ty_expr(psi: TypeExpr) -> Any:
    match psi:
        case Primitive():
            return Syntax.TyExprPrim(PRIM_TY[psi]())
        case ListExpr(elem):
            return Syntax.TyExprList(ty_expr(elem))
        case TupleExpr(components):
            return Syntax.TyExprTuple([ty_expr(c) for c in components])
        case DictExpr(value):
            return Syntax.TyExprDict(ty_expr(value))
        case CallableExpr(params, result):
            return Syntax.TyExprCallable([ty_expr(p) for p in params], ty_expr(result))
        case LiteralType(ell):
            return Syntax.TyExprLiteral(lit(ell.value))
        case TypeName(q, args):
            return Syntax.TyExprName(name(q), [ty_expr(a) for a in args])
        case UnionExpr(left, right):
            return Syntax.TyExprUnion(ty_expr(left), ty_expr(right))


def annotation(e: ast.expr | None) -> Any:
    return ty_expr(type_expr(e))


BOP: dict[type[ast.operator | ast.cmpop], Any] = {
    ast.BitOr: Syntax.BOpBitOr,
    ast.Eq: Syntax.BOpEq,
    ast.NotEq: Syntax.BOpNeq,
    ast.Lt: Syntax.BOpLt,
    ast.LtE: Syntax.BOpLeq,
    ast.Gt: Syntax.BOpGt,
    ast.GtE: Syntax.BOpGeq,
    ast.Add: Syntax.BOpAdd,
    ast.Sub: Syntax.BOpSub,
    ast.Mult: Syntax.BOpMul,
    ast.Div: Syntax.BOpDiv,
    ast.FloorDiv: Syntax.BOpFloorDiv,
    ast.Mod: Syntax.BOpMod,
    ast.Pow: Syntax.BOpPow,
    ast.In: Syntax.BOpIn,
    ast.NotIn: Syntax.BOpNotIn,
}

UOP: dict[type[ast.unaryop], Any] = {
    ast.Not: Syntax.UOpNot,
    ast.UAdd: Syntax.UOpPos,
    ast.USub: Syntax.UOpNeg,
}


def expr(e: ast.expr) -> Any:
    match e:
        case ast.Name(id=x):
            return Syntax.ExprVar(x)
        case ast.Constant(value=v):
            return Syntax.ExprLiteral(lit(v))
        case ast.Call(func=f, args=es, keywords=ks):
            return Syntax.ExprCall(expr(f), ([expr(e_) for e_ in es], [keyword(k) for k in ks]))
        case ast.Dict(values=vs):
            return Syntax.ExprDict([(expr(k), expr(v)) for k, v in zip(dict_keys(e), vs)])
        case ast.Attribute(value=e_, attr=x):
            return Syntax.ExprAttribute(expr(e_), x)
        case ast.Subscript(value=e_, slice=e__):
            return Syntax.ExprSubscript(expr(e_), expr(e__))
        case ast.BinOp(left=e_, op=op, right=e__):
            return Syntax.ExprBinOp(BOP[type(op)](), expr(e_), expr(e__))
        case ast.Compare(left=e_, ops=[op], comparators=[e__]):
            return Syntax.ExprBinOp(BOP[type(op)](), expr(e_), expr(e__))
        case ast.UnaryOp(op=op, operand=e_):
            return Syntax.ExprUnOp(UOP[type(op)](), expr(e_))
        case ast.BoolOp(op=ast.And(), values=[e_, e__]):
            return Syntax.ExprAnd(expr(e_), expr(e__))
        case ast.BoolOp(op=ast.Or(), values=[e_, e__]):
            return Syntax.ExprOr(expr(e_), expr(e__))
        case ast.IfExp(test=e_, body=e1, orelse=e2):
            return Syntax.ExprCond(expr(e1), expr(e_), expr(e2))
        case ast.List(elts=es):
            return Syntax.ExprList([expr(e_) for e_ in es])
        case ast.Tuple(elts=es):
            return Syntax.ExprTuple([expr(e_) for e_ in es])
        case ast.ListComp(elt=e_, generators=gs):
            return Syntax.ExprListComp(expr(e_), qualifiers(gs))
        case ast.DictComp(key=e_, value=e__, generators=gs):
            return Syntax.ExprDictComp(expr(e_), expr(e__), qualifiers(gs))
        case ast.Lambda(args=args, body=e_):
            return Syntax.ExprLambda([a.arg for a in args.args], expr(e_))
        case _:
            raise AssertionError(f"unexpected expression: {type(e).__name__}")


def keyword(k: ast.keyword) -> tuple[Any, Any]:
    assert k.arg is not None  # dictionary unpacking rejected by the parser
    return (k.arg, expr(k.value))


def qualifiers(gs: list[ast.comprehension]) -> list[Any]:
    return [
        q
        for g in gs
        for q in [
            Syntax.Generator(target_name(g), expr(g.iter)),
            *(Syntax.Guard(expr(c)) for c in g.ifs),
        ]
    ]


def pat(p: ast.pattern) -> Any:
    match p:
        case ast.MatchValue(value=ast.Constant(value=v)) | ast.MatchSingleton(value=v):
            return Syntax.PatLiteral(lit(v))
        case ast.MatchAs(pattern=None, name=None):
            return Syntax.PatWildcard()
        case ast.MatchAs(pattern=None, name=str(x)):
            return Syntax.PatVar(x)
        case ast.MatchAs(pattern=ast.pattern() as p_, name=str(x)):
            return Syntax.PatAs(pat(p_), x)
        case syntax.PatList(patterns=ps):
            return Syntax.PatList([pat(p_) for p_ in ps])
        case syntax.PatTuple(patterns=ps):
            return Syntax.PatTuple([pat(p_) for p_ in ps])
        case ast.MatchClass(cls=c, patterns=ps, kwd_attrs=xs, kwd_patterns=qs):
            q = dotted_name(c)
            assert q is not None  # other heads rejected by Python
            return Syntax.PatConstr(
                name(q), ([pat(p_) for p_ in ps], [(x, pat(q_)) for x, q_ in zip(xs, qs)])
            )
        case ast.MatchMapping(keys=ks, patterns=ps):
            return Syntax.PatDict([(key(k), pat(q)) for k, q in zip(ks, ps)])
        case _:
            raise AssertionError(f"unexpected pattern: {type(p).__name__}")


def key(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)  # others rejected by the parser
    return k.value


def stmt(s: ast.stmt) -> Any:
    match s:
        case ast.Pass():
            return Syntax.StmtPass()
        case ast.Assign(targets=[ast.Name(id=x)], value=e):
            return Syntax.StmtAssign(x, Option.None_(), expr(e))
        case ast.AnnAssign(target=ast.Name(id=x), annotation=a, value=None):
            return Syntax.StmtDeclare(x, annotation(a))
        case ast.AnnAssign(target=ast.Name(id=x), annotation=a, value=ast.expr() as e):
            return Syntax.StmtAssign(x, Option.Some(annotation(a)), expr(e))
        case ast.Expr(value=e):
            return Syntax.StmtExpr(expr(e))
        case ast.Assert(test=e, msg=e_):
            return Syntax.StmtAssert(expr(e), option(None if e_ is None else expr(e_)))
        case ast.Return(value=e):
            return Syntax.StmtReturn(option(None if e is None else expr(e)))
        case ast.If(test=e, body=ss, orelse=ss_):
            elifs, else_ = branches(s.col_offset, ss_)
            return Syntax.StmtIf(expr(e), seq(ss), elifs, else_)
        case ast.Match(subject=e, cases=bs):
            return Syntax.StmtMatch(expr(e), [(pat(b.pattern), seq(b.body)) for b in bs])
        case _:
            raise AssertionError(f"unexpected statement: {type(s).__name__}")


def branches(col: int, orelse: list[ast.stmt]) -> tuple[list[Any], Any]:
    """Recover the elifs, which Python parses as nested ifs. A nested if at the same column as the
    outer if is an elif."""
    match orelse:
        case []:
            return [], Option.None_()
        case [ast.If(test=e, body=ss, orelse=ss_) as s] if s.col_offset == col:
            elifs, else_ = branches(col, ss_)
            return [(expr(e), seq(ss)), *elifs], else_
        case _:
            return [], Option.Some(seq(orelse))


def seq(body: list[ast.stmt]) -> Any:
    *items, item = statements(body)
    return reduce(
        lambda s, item_: Syntax.StmtSeq(item_stmt(item_), s), reversed(items), item_stmt(item)
    )


def item_stmt(item: Statement) -> Any:
    match item:
        case ast.stmt():
            return stmt(item)
        case [ast.FunctionDef(), *_]:
            return Syntax.StmtMutualRegion([func(d) for d in item])
        case _:
            raise AssertionError("type definition outside the module top level")


def func(d: ast.stmt) -> Any:
    assert isinstance(d, ast.FunctionDef)  # mutual def regions hold only def statements
    return Syntax.Def(
        d.name,
        type_params(d),
        [(a.arg, annotation(a.annotation)) for a in d.args.args],
        annotation(d.returns),
        seq(d.body),
    )


def type_params(node: ast.FunctionDef | ast.ClassDef | ast.TypeAlias) -> list[Any]:
    return [alpha for alpha in type_param_names(node)]


def type_def(chi: ast.stmt) -> Any:
    match chi:
        case ast.ClassDef(name=c, bases=bases):
            fields = [(x, ty_expr(psi)) for x, psi in own_fields(chi)]
            return Syntax.Dataclass(c, type_params(chi), extends(bases), fields)
        case ast.TypeAlias(name=ast.Name(id=x), value=psi):
            return Syntax.TypeStmt(x, type_params(chi), annotation(psi))
        case _:
            raise AssertionError(f"unexpected type definition: {type(chi).__name__}")


def extends(bases: list[ast.expr]) -> Any:
    match bases:
        case []:
            return Option.None_()
        case [b]:
            psi = type_expr(b)
            assert isinstance(psi, TypeName)  # other base classes rejected by the parser
            return Option.Some((name(psi.q), [ty_expr(a) for a in psi.args]))
        case _:
            raise AssertionError("multiple inheritance")


def top_stmt(body: list[ast.stmt]) -> Any:
    *items, item = statements(body)
    return reduce(
        lambda s, item_: Syntax.TopSeq(top_item(item_), s), reversed(items), top_item(item)
    )


def top_item(item: Statement) -> Any:
    match item:
        case [ast.ClassDef() | ast.TypeAlias(), *_]:
            return Syntax.TypeDefs([type_def(chi) for chi in item])
        case _:
            return Syntax.Stmt(item_stmt(item))


def import_(iota: ast.stmt) -> Any:
    match iota:
        case ast.Import(names=[alias]):
            return Syntax.Import(name(parse_name(alias.name)))
        case ast.ImportFrom(module=str(q), names=aliases):
            return Syntax.FromImport(name(parse_name(q)), [a.name for a in aliases])
        case _:
            raise AssertionError(f"unexpected import: {type(iota).__name__}")


def module_body(q: Name, m: ast.Module) -> Any:
    iotas, stmts = split_imports(m.body)
    imports = [import_(iota) for iota in iotas]
    return Syntax.ModuleBody(imports, top_stmt([name_declaration(q), *stmts]))


def program(entry_path: pathlib.Path) -> Any:
    names = module_names(entry_path.parent) | {MAIN}
    parsed = parse_reachable(MAIN, {}, names, entry_path)
    # modules not reached by imports are left unparsed, with an empty body
    return Finite_Map.fmap_of_list(
        [
            (name(q), module_body(q, parsed.get(q, ast.Module(body=[], type_ignores=[]))))
            for q in sorted(names, key=str)
        ]
    )


def parse_reachable(
    q: Name, parsed: dict[Name, ast.Module], names: set[Name], entry_path: pathlib.Path
) -> dict[Name, ast.Module]:
    """Modules parsed when q is imported, in the order the reference checker parses them"""
    if q not in names or q in parsed:
        return parsed
    m = parse_module(q, entry_path)
    iotas, _ = split_imports(m.body)
    return reduce(
        lambda parsed_, q_: parse_reachable(q_, parsed_, names, entry_path),
        [q_ for iota in iotas for q_ in modules_checked(q, iota, names)],
        {**parsed, q: m},
    )


def modules_checked(q: Name, iota: ast.stmt, names: set[Name]) -> list[Name]:
    """Modules checked by an import statement of module q, in order"""
    match iota:
        case ast.Import(names=[alias]):
            q_ = parse_name(alias.name)
            return [*proper_prefixes(q_), q_]
        case ast.ImportFrom(module=str(q_s), names=aliases):
            q_ = parse_name(q_s)
            submodules = [p for a in aliases for p in [qualified(q_, a.name)] if p in names]
            return [q_, *containing(q, q_), *submodules]
        case _:
            raise AssertionError(f"unexpected import: {type(iota).__name__}")


def parse_module(q: Name, entry_path: pathlib.Path) -> ast.Module:
    try:
        return parse(path_of(q, entry_path))
    except syntax.Unsupported as e:
        e.module = q
        raise


def path_of(q: Name, entry_path: pathlib.Path) -> pathlib.Path:
    if q == MAIN:
        return entry_path
    path = module_path(q, entry_path.parent)
    # other names come from files and directories under the entry module's directory
    assert path is not None
    return path


def from_name(q: Any) -> Name:
    x, xs = q
    return Name((x, *xs))


def from_lit(ell: Any) -> Literal:
    match ell:
        case Syntax.LitInt(v) | Syntax.LitBool(v):
            return Literal(v)
        case Syntax.LitFloat(x):
            return Literal(x)
        case Syntax.LitString(s):
            return Literal(s)
        case Syntax.LitNone():
            return Literal(None)
        case _:
            raise AssertionError(f"unexpected literal: {ell}")


PRIMITIVE = {c: nu for nu, c in PRIM_TY.items()}


BOP_AST = {bop: op for op, bop in BOP.items()}
UOP_AST = {uop: op for op, uop in UOP.items()}


def from_expr(e: Any) -> ast.expr:
    match e:
        case Syntax.ExprVar(x):
            return ast.Name(x)
        case Syntax.ExprLiteral(ell):
            return ast.Constant(from_lit(ell).value)
        case Syntax.ExprCall(f, (es, kws)):
            return ast.Call(
                from_expr(f),
                [from_expr(e_) for e_ in es],
                [ast.keyword(x, from_expr(e_)) for x, e_ in kws],
            )
        case Syntax.ExprDict(kvs):
            return ast.Dict([from_expr(k) for k, _ in kvs], [from_expr(v) for _, v in kvs])
        case Syntax.ExprAttribute(e_, x):
            return ast.Attribute(from_expr(e_), x)
        case Syntax.ExprSubscript(e_, e__):
            return ast.Subscript(from_expr(e_), from_expr(e__))
        case Syntax.ExprBinOp(op, e_, e__):
            op_ = BOP_AST[type(op)]
            if issubclass(op_, ast.cmpop):
                return ast.Compare(from_expr(e_), [op_()], [from_expr(e__)])
            return ast.BinOp(from_expr(e_), op_(), from_expr(e__))
        case Syntax.ExprUnOp(op, e_):
            return ast.UnaryOp(UOP_AST[type(op)](), from_expr(e_))
        case Syntax.ExprAnd(e_, e__):
            return ast.BoolOp(ast.And(), [from_expr(e_), from_expr(e__)])
        case Syntax.ExprOr(e_, e__):
            return ast.BoolOp(ast.Or(), [from_expr(e_), from_expr(e__)])
        case Syntax.ExprCond(e_, e__, e___):
            return ast.IfExp(from_expr(e__), from_expr(e_), from_expr(e___))
        case Syntax.ExprList(es):
            return ast.List([from_expr(e_) for e_ in es])
        case Syntax.ExprTuple(es):
            return ast.Tuple([from_expr(e_) for e_ in es])
        case Syntax.ExprListComp(e_, qs):
            return ast.ListComp(from_expr(e_), reduce(add_qualifier, qs, []))
        case Syntax.ExprDictComp(e_, e__, qs):
            return ast.DictComp(from_expr(e_), from_expr(e__), reduce(add_qualifier, qs, []))
        case Syntax.ExprLambda(xs, e_):
            args = ast.arguments(
                posonlyargs=[],
                args=[ast.arg(x) for x in xs],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            )
            return ast.Lambda(args, from_expr(e_))
        case _:
            raise AssertionError(f"unexpected expression: {e}")


# Generator starts a comprehension; guard joins the last
def add_qualifier(gs: list[ast.comprehension], q: Any) -> list[ast.comprehension]:
    match q:
        case Syntax.Generator(x, e):
            return [*gs, ast.comprehension(ast.Name(x), from_expr(e), [], 0)]
        case Syntax.Guard(e):
            *gs_, g = gs
            return [*gs_, ast.comprehension(g.target, g.iter, [*g.ifs, from_expr(e)], 0)]
        case _:
            raise AssertionError(f"unexpected qualifier: {q}")


def from_ty(tau: Any) -> Type:
    match tau:
        case Syntax.TyPrim(nu):
            return PRIMITIVE[type(nu)]
        case Syntax.TyList(tau_):
            return ListType(from_ty(tau_))
        case Syntax.TyTuple(taus):
            return TupleType(tuple(from_ty(tau_) for tau_ in taus))
        case Syntax.TyDict(tau_):
            return DictType(from_ty(tau_))
        case Syntax.TyCallable(sigmas, tau_):
            return CallableType(tuple(from_ty(sigma) for sigma in sigmas), from_ty(tau_))
        case Syntax.TyLiteral(ell):
            return LiteralType(from_lit(ell))
        case Syntax.TyVar(alpha):
            return TypeVariable(alpha)
        case Syntax.TyClass(c, taus):
            return ClassType(ClassName(from_name(c)), tuple(from_ty(tau_) for tau_ in taus))
        case Syntax.TyUnion(sigma, tau_):
            return UnionType(from_ty(sigma), from_ty(tau_))
        case _:
            raise AssertionError(f"unexpected type: {tau}")


BINARY = {c: BINARY_NAMES[op] for op, c in BOP.items()}
UNARY = {c: UNARY_NAMES[op] for op, c in UOP.items()}


SEQUENCE_KIND = {
    Syntax.TupleKind(): "tuple",
    Syntax.ListKind(): "list",
    Syntax.RangeKind(): "range",
}


def render_pat(p: Any) -> str:
    match p:
        case Syntax.PatLiteral(ell):
            return ast.unparse(ast.Constant(from_lit(ell).value))
        case Syntax.PatVar(x):
            return str(x)
        case Syntax.PatWildcard():
            return "_"
        case Syntax.PatAs(p_, x):
            return f"{render_pat(p_)} as {x}"
        case Syntax.PatList(ps):
            return "[" + ", ".join(map(render_pat, ps)) + "]"
        case Syntax.PatTuple(ps):
            return "(" + ", ".join(map(render_pat, ps)) + ")"
        case Syntax.PatDict(kps):
            items = (f"{ast.unparse(ast.Constant(w))}: {render_pat(q)}" for w, q in kps)
            return "{" + ", ".join(items) + "}"
        case Syntax.PatConstr(q, (ps, kps)):
            args = [render_pat(p_) for p_ in ps] + [f"{x}={render_pat(p_)}" for x, p_ in kps]
            return f"{from_name(q)}({', '.join(args)})"
        case _:
            raise AssertionError(f"unexpected pattern: {p}")


def from_reason(r: Any) -> reasons.Reason:
    match r:
        case Reasons.DuplicateField(x, c):
            return reasons.DuplicateField(x, c)
        case Reasons.InheritedField(x, c, d):
            return reasons.InheritedField(x, c, d)
        case Reasons.UndefinedVariable(x):
            return reasons.UndefinedVariable(x)
        case Reasons.UnassignedVariable(x):
            return reasons.UnassignedVariable(x)
        case Reasons.PossiblyUnassigned(x, b):
            return reasons.PossiblyUnassigned(x, b)
        case Reasons.UnboundName(x):
            return reasons.UnboundName(x)
        case Reasons.Redeclaration(x):
            return reasons.Redeclaration(x)
        case Reasons.UndeclaredAssignment(x):
            return reasons.UndeclaredAssignment(x)
        case Reasons.AssignmentBeforeDeclaration(x):
            return reasons.AssignmentBeforeDeclaration(x)
        case Reasons.Reassignment(x):
            return reasons.Reassignment(x)
        case Reasons.PossibleReassignment(x):
            return reasons.PossibleReassignment(x)
        case Reasons.CapturedGeneratorVariable(x):
            return reasons.CapturedGeneratorVariable(x)
        case Reasons.UnreachableStatement():
            return reasons.UnreachableStatement()
        case Reasons.ConstructorArityMismatch(c, m, n):
            return reasons.ConstructorArityMismatch(c, m, n)
        case Reasons.UnknownConstructorKeyword(c, xs):
            return reasons.UnknownConstructorKeyword(c, tuple(xs))
        case Reasons.PatternArityMismatch(c, m, n):
            return reasons.PatternArityMismatch(c, m, n)
        case Reasons.UnknownFieldInPattern(c, xs):
            return reasons.UnknownFieldInPattern(c, tuple(xs))
        case Reasons.RangePattern():
            return reasons.RangePattern()
        case Reasons.PatternClassUndetermined(c, tau):
            return reasons.PatternClassUndetermined(c, from_ty(tau))
        case Reasons.SequenceKindMismatch(kind, tau, other):
            return reasons.SequenceKindMismatch(
                SEQUENCE_KIND[kind], from_ty(tau), SEQUENCE_KIND[other]
            )
        case Reasons.UnreachableCase(p):
            return reasons.UnreachableCase(render_pat(p))
        case Reasons.MissingReturnMatchPartial(tau):
            return reasons.MissingReturnMatchPartial(from_ty(tau))
        case Reasons.MissingReturnAssertion():
            return reasons.MissingReturnAssertion()
        case Reasons.NotPredefinedName(x):
            return reasons.NotPredefinedName(x)
        case Reasons.NotTypeExpression(e):
            return reasons.NotTypeExpression(ast.unparse(from_expr(e)))
        case Reasons.NotClass(q):
            return reasons.NotClass(from_name(q))
        case Reasons.ClassArityMismatch(q, m, n):
            return reasons.ClassArityMismatch(from_name(q), m, n)
        case Reasons.TypeAliasArityMismatch(q, m, n):
            return reasons.TypeAliasArityMismatch(from_name(q), m, n)
        case Reasons.CyclicTypeAlias(x):
            return reasons.CyclicTypeAlias(x)
        case Reasons.DuplicateMember(x, q):
            return reasons.DuplicateMember(x, from_name(q))
        case Reasons.SubmoduleNotImported(q):
            return reasons.SubmoduleNotImported(from_name(q))
        case Reasons.UnassignedMember(x, q):
            return reasons.UnassignedMember(x, from_name(q))
        case Reasons.TopLevelAssertFalse():
            return reasons.TopLevelAssertFalse()
        case Reasons.UnknownModule(q):
            return reasons.UnknownModule(from_name(q))
        case Reasons.DuplicateImportedName(x):
            return reasons.DuplicateImportedName(x)
        case Reasons.UnknownMember(x, q):
            return reasons.UnknownMember(x, from_name(q))
        case Reasons.ModuleAsValue(q):
            return reasons.ModuleAsValue(from_name(q))
        case Reasons.ImportOfContainedModule(q, q_):
            return reasons.ImportOfContainedModule(from_name(q), from_name(q_))
        case Reasons.PredefinedNameAsValue(q):
            return reasons.PredefinedNameAsValue(from_name(q))
        case Reasons.TypeParameterAsValue(x):
            return reasons.TypeParameterAsValue(x)
        case Reasons.TypeSchemeAsValue(q):
            return reasons.TypeSchemeAsValue(from_name(q))
        case Reasons.NoTypeArgument(alpha):
            return reasons.NoTypeArgument(alpha)
        case Reasons.ClassAsValue(q):
            return reasons.ClassAsValue(from_name(q))
        case Reasons.TypeAliasAsValue(q):
            return reasons.TypeAliasAsValue(from_name(q))
        case Reasons.NoBinaryOverload(op, sigma, sigma_):
            return reasons.NoBinaryOverload(BINARY[type(op)], from_ty(sigma), from_ty(sigma_))
        case Reasons.NoUnaryOverload(op, sigma):
            return reasons.NoUnaryOverload(UNARY[type(op)], from_ty(sigma))
        case Reasons.NotCallable(tau):
            return reasons.NotCallable(from_ty(tau))
        case Reasons.KeywordArgumentsNotConstructor():
            return reasons.KeywordArgumentsNotConstructor()
        case Reasons.CallArityMismatch(m, n):
            return reasons.CallArityMismatch(m, n)
        case Reasons.NoneResult():
            return reasons.NoneResult()
        case Reasons.TypeMismatch(tau, sigma):
            return reasons.TypeMismatch(from_ty(tau), from_ty(sigma))
        case Reasons.LambdaTypeMismatch(tau, Option.Some(n)):
            return reasons.LambdaTypeMismatch(from_ty(tau), n)
        case Reasons.LambdaTypeMismatch(tau, Option.None_()):
            return reasons.LambdaTypeMismatch(from_ty(tau), None)
        case Reasons.NotSubscriptable(tau):
            return reasons.NotSubscriptable(from_ty(tau))
        case Reasons.TupleIndexOutOfRange(i, n):
            return reasons.TupleIndexOutOfRange(i, n)
        case Reasons.NotIterable(tau):
            return reasons.NotIterable(from_ty(tau))
        case Reasons.NotSynthesised():
            return reasons.NotSynthesised()
        case Reasons.UnknownField(c, x):
            return reasons.UnknownField(c, x)
        case Reasons.NoAttributes(tau):
            return reasons.NoAttributes(from_ty(tau))
        case Reasons.BareReturn(tau):
            return reasons.BareReturn(from_ty(tau))
        case Reasons.MissingReturn(x, tau):
            return reasons.MissingReturn(x, from_ty(tau))
        case _:
            raise AssertionError(f"unexpected reason: {r}")


NO_POSITION = ast.AST()


def ill_formed(q: Any, r: Any) -> IllFormed:
    """Failure for reason r in module q"""
    match r:
        case Reasons.ImportCycle(qs):
            return IllFormedProgram(reasons.ImportCycle(tuple(map(from_name, qs))).message())
        case Reasons.MypyCompatibility(r_):
            e: IllFormedModule = MypyCompatibility(NO_POSITION, from_reason(r_))
        case _:
            e = IllFormedModule(NO_POSITION, from_reason(r))
    e.module = from_name(q)
    return e


def check(M: Any) -> IllFormed | None:
    match Programs.check_program(M):
        case Option.None_():
            return None
        case Option.Some((q, r)):
            return ill_formed(q, r)
        case result:
            raise AssertionError(f"unexpected result: {result}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="purepy-generated")
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        parser.error("running programs not yet implemented")
    try:
        result = check(program(args.path))
    except syntax.Unsupported as e:
        print(format_program_result(e, args.path))
        sys.exit(e.exit_code)
    if result is None:
        print(f"{args.path}: ok")
        sys.exit(Exit.OK)
    print(f"{error_path(result, args.path)}: {result.msg}")
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
