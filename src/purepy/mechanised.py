"""Translation of parsed modules into the mechanised syntax, and the type checker generated from the
mechanisation as a checker command; the generated code is on PYTHONPATH"""

import argparse
import ast
import math
import pathlib
import sys
from typing import Any

import Finite_Map
import Option
import Rat
import Real
import String
import Syntax
import Typing

from . import syntax
from .check_module import name_declaration
from .check_program import format_program_result, module_names, module_path, parse
from .conformance import Exit
from .contexts import MAIN
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
    DictExpr,
    ListExpr,
    LiteralType,
    Name,
    Primitive,
    TupleExpr,
    TypeExpr,
    TypeName,
    UnionExpr,
    dotted_name,
    parse_name,
)

OUTSIDE_FRAGMENT = 5


class OutsideFragment(Exception):
    pass


def string(s: str) -> list[Any]:
    """Isabelle string: list of eight-bit characters, least significant bit first"""
    if any(ord(c) > 255 for c in s):
        raise OutsideFragment(f"string {s!r} with a character outside Latin-1")
    return [String.Char(*(((ord(c) >> i) & 1) == 1 for i in range(8))) for c in s]


def real(x: float) -> Any:
    """Float as the real it denotes, since floats are reals in the mechanisation"""
    if not math.isfinite(x):
        raise OutsideFragment(f"float {x} outside the reals")
    return Real.Ratreal(Rat.Frct(x.as_integer_ratio()))


def lit(v: object) -> Any:
    match v:
        case bool():
            return Syntax.LitBool(v)
        case int():
            return Syntax.LitInt(v)
        case float():
            return Syntax.LitFloat(real(v))
        case str():
            return Syntax.LitString(string(v))
        case None:
            return Syntax.LitNone()
        case _:
            raise AssertionError(f"unexpected literal: {type(v).__name__}")


def name(q: Name) -> Any:
    return (string(q.parts[0]), [string(x) for x in q.parts[1:]])


def option(x: Any) -> Any:
    return Option.Nonea() if x is None else Option.Some(x)


PRIM_TY = {
    Primitive.OBJECT: Syntax.object,
    Primitive.NEVER: Syntax.Never,
    Primitive.NONE: Syntax.NoneType,
    Primitive.BOOL: Syntax.bool,
    Primitive.INT: Syntax.int,
    Primitive.FLOAT: Syntax.float,
    Primitive.STR: Syntax.str,
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


BOP = {
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

UOP = {ast.Not: Syntax.UOpNot, ast.UAdd: Syntax.UOpPos, ast.USub: Syntax.UOpNeg}


def expr(e: ast.expr) -> Any:
    match e:
        case ast.Name(id=x):
            return Syntax.ExprVar(string(x))
        case ast.Constant(value=v):
            return Syntax.ExprLiteral(lit(v))
        case ast.Call(func=f, args=es, keywords=ks):
            return Syntax.ExprCall(expr(f), (exprs(es), [keyword(k) for k in ks]))
        case ast.Dict(values=vs):
            return Syntax.ExprDict([(expr(k), expr(v)) for k, v in zip(dict_keys(e), vs)])
        case ast.Attribute(value=e_, attr=x):
            return Syntax.ExprAttribute(expr(e_), string(x))
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
            return Syntax.ExprList(exprs(es))
        case ast.Tuple(elts=es):
            return Syntax.ExprTuple(exprs(es))
        case ast.ListComp(elt=e_, generators=gs):
            return Syntax.ExprListComp(expr(e_), qualifiers(gs))
        case ast.DictComp(key=e_, value=e__, generators=gs):
            return Syntax.ExprDictComp(expr(e_), expr(e__), qualifiers(gs))
        case ast.Lambda(args=args, body=e_):
            return Syntax.ExprLambda([string(a.arg) for a in args.args], expr(e_))
        case _:
            raise AssertionError(f"unexpected expression: {type(e).__name__}")


def exprs(es: list[ast.expr]) -> list[Any]:
    return [expr(e) for e in es]


def keyword(k: ast.keyword) -> tuple[Any, Any]:
    assert k.arg is not None  # dictionary unpacking rejected by the parser
    return (string(k.arg), expr(k.value))


def qualifiers(gs: list[ast.comprehension]) -> list[Any]:
    return [
        q
        for g in gs
        for q in [
            Syntax.Generator(string(target_name(g)), expr(g.iter)),
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
            return Syntax.PatVar(string(x))
        case ast.MatchAs(pattern=ast.pattern() as p_, name=str(x)):
            return Syntax.PatAs(pat(p_), string(x))
        case syntax.PatList(patterns=ps):
            return Syntax.PatList(pats(ps))
        case syntax.PatTuple(patterns=ps):
            return Syntax.PatTuple(pats(ps))
        case ast.MatchClass(cls=c, patterns=ps, kwd_attrs=xs, kwd_patterns=qs):
            q = dotted_name(c)
            assert q is not None  # other heads rejected by Python
            return Syntax.PatConstr(
                name(q), (pats(ps), [(string(x), pat(q_)) for x, q_ in zip(xs, qs)])
            )
        case ast.MatchMapping(keys=ks, patterns=ps):
            return Syntax.PatDict([(string(key(k)), pat(q)) for k, q in zip(ks, ps)])
        case _:
            raise AssertionError(f"unexpected pattern: {type(p).__name__}")


def pats(ps: list[ast.pattern]) -> list[Any]:
    return [pat(p) for p in ps]


def key(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)  # others rejected by the parser
    return k.value


def stmt(s: ast.stmt) -> Any:
    match s:
        case ast.Pass():
            return Syntax.StmtPass()
        case ast.Assign(targets=[ast.Name(id=x)], value=e):
            return Syntax.StmtAssign(string(x), Option.Nonea(), expr(e))
        case ast.AnnAssign(target=ast.Name(id=x), annotation=a, value=None):
            return Syntax.StmtDeclare(string(x), annotation(a))
        case ast.AnnAssign(target=ast.Name(id=x), annotation=a, value=ast.expr() as e):
            return Syntax.StmtAssign(string(x), Option.Some(annotation(a)), expr(e))
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
    """Elif branches and else branch of an if statement at column col; Python's AST represents an elif
    as an if statement alone in the else branch, at the same column"""
    match orelse:
        case []:
            return [], Option.Nonea()
        case [ast.If(test=e, body=ss, orelse=ss_) as s] if s.col_offset == col:
            elifs, else_ = branches(col, ss_)
            return [(expr(e), seq(ss)), *elifs], else_
        case _:
            return [], Option.Some(seq(orelse))


def seq(body: list[ast.stmt]) -> Any:
    return seq_items(statements(body))


def seq_items(items: list[Statement]) -> Any:
    match items:
        case [item]:
            return item_stmt(item)
        case [item, *rest]:
            return Syntax.StmtSeq(item_stmt(item), seq_items(rest))
        case _:
            raise AssertionError("empty body")


def item_stmt(item: Statement) -> Any:
    match item:
        case ast.stmt():
            return stmt(item)
        case [ast.FunctionDef(), *_]:
            return Syntax.StmtMutualRegion([func(d) for d in item])
        case _:
            raise AssertionError("type definition outside the module top level")


def func(d: ast.stmt) -> Any:
    assert isinstance(d, ast.FunctionDef)  # a region of function definitions holds nothing else
    return Syntax.Def(
        string(d.name),
        type_params(d),
        [(string(a.arg), annotation(a.annotation)) for a in d.args.args],
        annotation(d.returns),
        seq(d.body),
    )


def type_params(node: ast.FunctionDef | ast.ClassDef | ast.TypeAlias) -> list[Any]:
    return [string(alpha) for alpha in type_param_names(node)]


def type_def(chi: ast.stmt) -> Any:
    match chi:
        case ast.ClassDef(name=c, bases=bases):
            fields = [(string(x), ty_expr(psi)) for x, psi in own_fields(chi)]
            return Syntax.Dataclass(string(c), type_params(chi), extends(bases), fields)
        case ast.TypeAlias(name=ast.Name(id=x), value=psi):
            return Syntax.TypeAlias(string(x), type_params(chi), annotation(psi))
        case _:
            raise AssertionError(f"unexpected type definition: {type(chi).__name__}")


def extends(bases: list[ast.expr]) -> Any:
    match bases:
        case []:
            return Option.Nonea()
        case [b]:
            psi = type_expr(b)
            assert isinstance(psi, TypeName)  # other base classes rejected by the parser
            return Option.Some((name(psi.q), [ty_expr(a) for a in psi.args]))
        case _:
            raise AssertionError("multiple inheritance")


def top_stmt(items: list[Statement]) -> Any:
    match items:
        case [item]:
            return top_item(item)
        case [item, *rest]:
            return Syntax.TopSeq(top_item(item), top_stmt(rest))
        case _:
            raise AssertionError("empty module body")


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
            return Syntax.FromImport(name(parse_name(q)), [string(a.name) for a in aliases])
        case _:
            raise AssertionError(f"unexpected import: {type(iota).__name__}")


def module_body(q: Name, m: ast.Module) -> Any:
    """Body of module q, beginning with the declaration of its name as the spec defines a module body"""
    iotas, stmts = split_imports(m.body)
    imports = [import_(iota) for iota in iotas]
    return Syntax.ModuleBody(imports, top_stmt(statements([name_declaration(q), *stmts])))


def module_table(entry_path: pathlib.Path) -> Any:
    """Program of the entry module and every module under its directory, each parsed up front"""
    names = sorted(module_names(entry_path.parent) | {MAIN}, key=str)
    return Finite_Map.fmap_of_list(
        [(name(q), module_body(q, parse_module(q, entry_path))) for q in names]
    )


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
    assert path is not None  # every other name is that of a file or directory under the entry's
    return path


def check(M: Any) -> bool:
    accepted = Typing.check_program(M)
    assert isinstance(accepted, bool)
    return accepted


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="purepy-mechanised",
        description="Check a program from its entry module with the type checker generated from the "
        "mechanisation, with the generated code on PYTHONPATH; exits with the codes of the reference "
        f"checker, or with {OUTSIDE_FRAGMENT} for a program outside the mechanised fragment",
    )
    parser.add_argument("path", type=pathlib.Path)
    args = parser.parse_args()
    try:
        ok = check(module_table(args.path))
    except syntax.Unsupported as e:
        print(format_program_result(e, args.path))
        sys.exit(e.exit_code)
    except OutsideFragment as e:
        print(f"{args.path}: outside the mechanised fragment: {e}")
        sys.exit(OUTSIDE_FRAGMENT)
    print(f"{args.path}: {'ok' if ok else 'ill-formed'}")
    sys.exit(Exit.OK if ok else Exit.ILL_FORMED)


if __name__ == "__main__":
    main()
