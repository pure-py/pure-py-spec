import ast
from collections.abc import Sequence
from functools import reduce
from itertools import takewhile
from typing import Any

from .generated import Option, Positions, Syntax

# Sorts of the mechanisation, Any until the generator annotates them: #7, Type annotations in generated code,
# https://github.com/ourlang/isabelle-python-codegen/issues/7
type Var = str
type Pos = tuple[int, int]
type Located = Any
type QualifiedName = Any
type Lit = Any
type Pat = Any
type Expr = Any
type Qualifier = Any
type TyExpr = Any
type Ty = Any
type Import = Any
type Stmt = Any
type Func = Any
type TypeDef = Any
type TopStmt = Any
type ModuleBody = Any
type Program = Any
type Reason = Any
# Name as a tuple of variables, hashable unlike the generated form; delete with #24, Names as a datatype,
# https://github.com/ourlang/mechanisation/issues/24
type Name = tuple[Var, ...]


def parse_name(name: str) -> Name:
    return tuple(name.split("."))


def is_import(s: ast.stmt) -> bool:
    return isinstance(s, (ast.Import, ast.ImportFrom))


def split_imports(body: list[ast.stmt]) -> tuple[list[ast.stmt], list[ast.stmt]]:
    iotas = list(takewhile(is_import, body))
    return iotas, body[len(iotas) :]


SYMBOL: dict[type, str] = {
    ast.BitOr: "|",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.In: "in",
    ast.NotIn: "not in",
    ast.Not: "not",
    ast.UAdd: "+",
    ast.USub: "-",
    ast.BitAnd: "&",
    ast.BitXor: "^",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.MatMult: "@",
    ast.Invert: "~",
}


class ParserRejects(Exception):
    msg: str
    module: Name | None = None

    def __init__(self, msg: str, line: int | None, col: int | None):
        self.msg = msg
        self.line = line
        self.col = col
        super().__init__(msg)


def node_position(node: ast.AST) -> tuple[int | None, int | None]:
    """Line and column of node, or None if node doesn't have a position, like a function's arguments"""
    return getattr(node, "lineno", None), getattr(node, "col_offset", None)


class PythonRejects(ParserRejects):
    """Rejection shared with Python: a syntax error from Python's parser, or a condition of the syntax such
    as distinct parameters"""


def python_rejects(e: SyntaxError) -> PythonRejects:
    return PythonRejects(e.msg, e.lineno, None if e.offset is None else e.offset - 1)


def not_allowed(construct: str) -> str:
    return f"{construct} not allowed in OurLang"


class SyntacticallyExcluded(ParserRejects):
    def __init__(self, node: ast.AST, construct: str):
        super().__init__(not_allowed(construct), *node_position(node))


def parse(source: str, filename: str) -> ast.Module:
    """Parse, marking sequence patterns in square brackets as list patterns, since Python's syntax tree
    doesn't record the brackets"""
    m = ast.parse(source, filename=filename)
    for node_ in ast.walk(m):
        if isinstance(node_, ast.MatchSequence):
            segment = ast.get_source_segment(source, node_)
            assert segment is not None
            setattr(node_, "list", segment.startswith("["))  # noqa: B010
    return m


def duplicate[T](xs: Sequence[T]) -> T | None:
    """An element occurring twice in xs, if any"""
    return next((x for i, x in enumerate(xs) if x in xs[:i]), None)


def option(x: Any) -> Any:
    return Option.None_() if x is None else Option.Some(x)


def position(node: ast.expr | ast.stmt | ast.pattern) -> Pos:
    return (node.lineno, node.col_offset)


def at(node: ast.expr | ast.stmt | ast.pattern, term: Any) -> Located:
    return Positions.At(position(node), term)


def located_at(t: Located) -> Pos:
    match t:
        case Positions.At((line, col), _):
            return (line, col)
        case _:
            raise AssertionError(f"unlocated term: {t}")


def node(t: Located) -> Any:
    match t:
        case Positions.At(_, u):
            return u
        case _:
            raise AssertionError(f"unlocated term: {t}")


type Statement = ast.stmt | list[ast.FunctionDef] | list[ast.ClassDef | ast.TypeAlias]


def statements(body: list[ast.stmt]) -> list[Statement]:
    if len(body) == 0:
        return []
    head = body[0]
    rest = body[1:]
    if isinstance(head, ast.FunctionDef):
        return extend_def_region([head], rest)
    if isinstance(head, (ast.ClassDef, ast.TypeAlias)):
        return extend_type_region([head], rest)
    return [head] + statements(rest)


def extend_def_region(region: list[ast.FunctionDef], rest: list[ast.stmt]) -> list[Statement]:
    if len(rest) == 0:
        return [region]
    head = rest[0]
    if isinstance(head, ast.FunctionDef):
        return extend_def_region(region + [head], rest[1:])
    return [region] + statements(rest)


def extend_type_region(
    region: list[ast.ClassDef | ast.TypeAlias], rest: list[ast.stmt]
) -> list[Statement]:
    if len(rest) == 0:
        return [region]
    head = rest[0]
    if isinstance(head, (ast.ClassDef, ast.TypeAlias)):
        return extend_type_region(region + [head], rest[1:])
    return [region] + statements(rest)


def lit(v: object) -> Lit:
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


def name(e: ast.expr) -> Name | None:
    match e:
        case ast.Name(id=x):
            return (x,)
        case ast.Attribute(value=e_, attr=x):
            q = name(e_)
            return None if q is None else (*q, x)
        case _:
            return None


def qualified_name(q: Name) -> QualifiedName:
    return (q[0], list(q[1:]))


PRIM_TY = {
    "object": Syntax.object_,
    "Never": Syntax.Never,
    "None": Syntax.NoneType,
    "bool": Syntax.bool_,
    "int": Syntax.int_,
    "float": Syntax.float_,
    "str": Syntax.str_,
    "Sized": Syntax.Sized,
}
PRIMITIVE = {c: x for x, c in PRIM_TY.items()}


def ty_expr(e: ast.expr) -> TyExpr | None:
    match e:
        case ast.Constant(value=None):
            return Syntax.TyExprPrim(Syntax.NoneType())
        case ast.Name(id=x) if x in PRIM_TY:
            return Syntax.TyExprPrim(PRIM_TY[x]())
        case ast.Name() | ast.Attribute():
            q = name(e)
            return None if q is None else Syntax.TyExprName(qualified_name(q), [])
        case ast.BinOp(left=e1, op=ast.BitOr(), right=e2):
            psi, psi_ = ty_expr(e1), ty_expr(e2)
            return None if psi is None or psi_ is None else Syntax.TyExprUnion(psi, psi_)
        case ast.Subscript(value=ast.Name(id="Literal"), slice=s):
            match s:
                case ast.Constant(value=bool() | int() | str() | None as v):
                    return Syntax.TyExprLiteral(lit(v))
                case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=int() as n)) if (
                    type(n) is not bool
                ):
                    return Syntax.TyExprLiteral(lit(-n))
                case _:
                    return None
        case ast.Subscript(value=ast.Name(id="Callable"), slice=s):
            match s:
                case ast.Tuple(elts=[ast.List(elts=es), e_]):
                    psis, psi = ty_exprs(es), ty_expr(e_)
                    return None if psis is None or psi is None else Syntax.TyExprCallable(psis, psi)
                case _:
                    return None
        case ast.Subscript(value=head, slice=s):
            psis = ty_exprs(s.elts if isinstance(s, ast.Tuple) else [s])
            if psis is None:
                return None
            match head, psis:
                case ast.Name(id="list"), [psi]:
                    return Syntax.TyExprList(psi)
                case ast.Name(id="list"), _:
                    return None
                case ast.Name(id="tuple"), _:
                    return Syntax.TyExprTuple(psis)
                case ast.Name(id="dict"), [Syntax.TyExprPrim(Syntax.str_()), psi]:
                    return Syntax.TyExprDict(psi)
                case ast.Name(id="dict"), _:
                    return None
                case _:
                    q = name(head)
                    return None if q is None else Syntax.TyExprName(qualified_name(q), psis)
        case _:
            return None


def ty_exprs(es: list[ast.expr]) -> list[TyExpr] | None:
    psis = [ty_expr(e) for e in es]
    return None if any(psi is None for psi in psis) else psis


def annotation(e: ast.expr | None) -> TyExpr:
    assert e is not None  # missing annotations rejected by the parser
    psi = ty_expr(e)
    if psi is None:
        raise SyntacticallyExcluded(e, "annotation that is not a type expression")
    return psi


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
BOP_AST = {bop: op for op, bop in BOP.items()}
UOP_AST = {uop: op for op, uop in UOP.items()}


def expr(e: ast.expr) -> Expr:
    return at(e, expr_node(e))


def expr_node(e: ast.expr) -> Expr:
    match e:
        case ast.Name(id=x):
            return Syntax.ExprVar(x)
        case ast.Constant(value=v):
            if not isinstance(v, (int, float, str, bool, type(None))):
                raise SyntacticallyExcluded(e, f"{type(v).__name__} literal")
            return Syntax.ExprLiteral(lit(v))
        case ast.Call(func=f, args=es, keywords=ks):
            f_ = expr(f)
            es_ = [expr(e_) for e_ in es]
            ks_ = [keyword(k) for k in ks]
            dup = duplicate([k.arg for k in ks])
            if dup is not None:
                raise PythonRejects(f"duplicate keyword argument {dup}", *node_position(e))
            return Syntax.ExprCall(f_, (es_, ks_))
        case ast.Dict(keys=ks, values=vs):
            if any(k is None for k in ks):
                raise SyntacticallyExcluded(e, "dictionary unpacking")
            ks_ = [expr(k) for k in ks if k is not None]
            return Syntax.ExprDict(list(zip(ks_, [expr(v) for v in vs])))
        case ast.Attribute(value=e_, attr=x):
            return Syntax.ExprAttribute(expr(e_), x)
        case ast.Subscript(value=e_, slice=e__):
            return Syntax.ExprSubscript(expr(e_), expr(e__))
        case ast.BinOp(op=op) if type(op) not in BOP:
            raise SyntacticallyExcluded(
                e, f"binary operator '{SYMBOL.get(type(op), type(op).__name__)}'"
            )
        case ast.BinOp(left=e_, op=op, right=e__):
            return Syntax.ExprBinOp(BOP[type(op)](), expr(e_), expr(e__))
        case ast.Compare(ops=[_, _, *_]):
            raise SyntacticallyExcluded(e, "chained comparison")
        case ast.Compare(ops=[ast.Is() | ast.IsNot()]):
            raise SyntacticallyExcluded(e, "identity operator (is/is not)")
        case ast.Compare(left=e_, ops=[op], comparators=[e__]):
            return Syntax.ExprBinOp(BOP[type(op)](), expr(e_), expr(e__))
        case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=int() | float() as n)) if (
            type(n) is not bool
        ):
            return Syntax.ExprLiteral(lit(-n))
        case ast.UnaryOp(op=op) if type(op) not in UOP:
            raise SyntacticallyExcluded(
                e, f"unary operator '{SYMBOL.get(type(op), type(op).__name__)}'"
            )
        case ast.UnaryOp(op=op, operand=e_):
            return Syntax.ExprUnOp(UOP[type(op)](), expr(e_))
        case ast.BoolOp(values=[_, _, _, *_]):
            raise SyntacticallyExcluded(e, "chained boolean operator")
        case ast.BoolOp(op=ast.And(), values=[e_, e__]):
            return Syntax.ExprAnd(expr(e_), expr(e__))
        case ast.BoolOp(op=ast.Or(), values=[e_, e__]):
            return Syntax.ExprOr(expr(e_), expr(e__))
        case ast.IfExp(test=e_, body=e1, orelse=e2):
            e_t = expr(e_)
            return Syntax.ExprCond(expr(e1), e_t, expr(e2))
        case ast.List(elts=es):
            return Syntax.ExprList([expr(e_) for e_ in es])
        case ast.Tuple(elts=es):
            return Syntax.ExprTuple([expr(e_) for e_ in es])
        case ast.ListComp(elt=e_, generators=gs):
            return Syntax.ExprListComp(expr(e_), qualifiers(gs))
        case ast.DictComp(key=e_, value=e__, generators=gs):
            k = expr(e_)
            return Syntax.ExprDictComp(k, expr(e__), qualifiers(gs))
        case ast.Lambda(args=args, body=e_):
            xs = [a.arg for a in params(args)]
            return Syntax.ExprLambda(xs, expr(e_))
        case ast.Set():
            raise SyntacticallyExcluded(e, "set literals")
        case ast.SetComp():
            raise SyntacticallyExcluded(e, "set comprehensions")
        case ast.Slice():
            raise SyntacticallyExcluded(e, "slicing")
        case ast.GeneratorExp():
            raise SyntacticallyExcluded(e, "generator expressions")
        case ast.NamedExpr():
            raise SyntacticallyExcluded(e, "walrus operator (:=)")
        case ast.Starred():
            raise SyntacticallyExcluded(e, "starred expressions")
        case ast.Await():
            raise SyntacticallyExcluded(e, "async")
        case ast.Yield() | ast.YieldFrom():
            raise SyntacticallyExcluded(e, "yield")
        case ast.JoinedStr() | ast.FormattedValue():
            raise SyntacticallyExcluded(e, "f-strings")
        case _:
            raise SyntacticallyExcluded(e, f"{type(e).__name__} expression")


def keyword(k: ast.keyword) -> tuple[str, Expr]:
    if k.arg is None:
        raise SyntacticallyExcluded(k, "dictionary unpacking in argument list")
    return (k.arg, expr(k.value))


def params(args: ast.arguments) -> list[ast.arg]:
    if args.vararg is not None:
        raise SyntacticallyExcluded(args, "*args")
    if args.kwarg is not None:
        raise SyntacticallyExcluded(args, "**kwargs")
    if len(args.kwonlyargs) > 0:
        raise SyntacticallyExcluded(args, "keyword-only arguments")
    if len(args.defaults) > 0 or len(args.kw_defaults) > 0:
        raise SyntacticallyExcluded(args, "default arguments")
    if len(args.posonlyargs) > 0:
        raise SyntacticallyExcluded(args, "positional-only arguments")
    dup = duplicate([a.arg for a in args.args])
    if dup is not None:
        raise PythonRejects(f"duplicate parameter {dup}", *node_position(args))
    return args.args


def qualifiers(gs: list[ast.comprehension]) -> list[Qualifier]:
    return [q for g in gs for q in qualifier(g)]


def qualifier(g: ast.comprehension) -> list[Qualifier]:
    """Generator located at its variable, since Python's syntax tree doesn't give the generator a position"""
    match g:
        case ast.comprehension(is_async=1):
            raise SyntacticallyExcluded(g, "async comprehensions")
        case ast.comprehension(target=ast.Name(id=x), iter=e, ifs=cs):
            return [
                at(g.target, Syntax.Generator(x, expr(e))),
                *(at(c, Syntax.Guard(expr(c))) for c in cs),
            ]
        case _:
            raise SyntacticallyExcluded(g, "unpacking in comprehensions")


def bound(pattern: ast.pattern) -> list[Var]:
    """Variables bound by pattern, in order and with repetitions"""
    match pattern:
        case ast.MatchValue() | ast.MatchSingleton():
            return []
        case ast.MatchAs(pattern=p, name=x):
            return (bound(p) if p is not None else []) + ([x] if x else [])
        case ast.MatchSequence(patterns=ps) | ast.MatchMapping(patterns=ps):
            return [x for p in ps for x in bound(p)]
        case ast.MatchClass(patterns=ps, kwd_patterns=ps_):
            return [x for p in list(ps) + list(ps_) for x in bound(p)]
        case _:
            raise AssertionError(f"unexpected pattern: {type(pattern).__name__}")


def pat(p: ast.pattern) -> Pat:
    return at(p, pat_node(p))


def pat_node(p: ast.pattern) -> Pat:
    match p:
        case ast.MatchValue(value=ast.Constant(value=int() | float() | str() as v)):
            return Syntax.PatLiteral(lit(v))
        case ast.MatchValue(
            value=ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=int() | float() as n))
        ) if type(n) is not bool:
            return Syntax.PatLiteral(lit(-n))
        case ast.MatchValue(value=ast.Attribute()):
            raise SyntacticallyExcluded(p, "attribute value patterns")
        case ast.MatchValue():
            raise SyntacticallyExcluded(p, "complex and bytes literal patterns")
        case ast.MatchSingleton(value=v):
            return Syntax.PatLiteral(lit(v))
        case ast.MatchAs(pattern=None, name=None):
            return Syntax.PatWildcard()
        case ast.MatchAs(pattern=None, name=str(x)):
            return Syntax.PatVar(x)
        case ast.MatchAs(pattern=ast.pattern() as p_, name=str(x)):
            return Syntax.PatAs(pat(p_), x)
        case ast.MatchSequence(patterns=ps) if getattr(p, "list", False):
            return Syntax.PatList([pat(p_) for p_ in ps])
        case ast.MatchSequence(patterns=ps):
            return Syntax.PatTuple([pat(p_) for p_ in ps])
        case ast.MatchClass(cls=c, patterns=ps, kwd_attrs=xs, kwd_patterns=qs):
            q = name(c)
            assert q is not None  # other heads rejected by Python
            ps_ = [pat(p_) for p_ in ps]
            qs_ = [pat(q_) for q_ in qs]
            dup = duplicate(xs)
            if dup is not None:
                raise PythonRejects(
                    f"duplicate keyword {dup} in constructor pattern", *node_position(p)
                )
            return Syntax.PatConstr(qualified_name(q), (ps_, list(zip(xs, qs_))))
        case ast.MatchMapping(rest=str()):
            raise SyntacticallyExcluded(p, "rest capture in dictionary patterns")
        case ast.MatchMapping(keys=ks, patterns=ps):
            ws = [key(k) for k in ks]
            dup = duplicate(ws)
            if dup is not None:
                raise PythonRejects(
                    f"duplicate key '{dup}' in dictionary pattern", *node_position(p)
                )
            return Syntax.PatDict([(w, pat(q)) for w, q in zip(ws, ps)])
        case ast.MatchOr():
            raise SyntacticallyExcluded(p, "or-patterns")
        case ast.MatchStar():
            raise SyntacticallyExcluded(p, "star patterns")
        case _:
            raise SyntacticallyExcluded(p, f"{type(p).__name__} pattern")


def key(k: ast.expr) -> str:
    match k:
        case ast.Constant(value=str(w)):
            return w
        case _:
            raise SyntacticallyExcluded(k, "dictionary pattern key other than a string literal")


def stmt(s: ast.stmt) -> Stmt:
    return at(s, stmt_node(s))


def stmt_node(s: ast.stmt) -> Stmt:
    match s:
        case ast.Pass():
            return Syntax.StmtPass()
        case ast.Assign(targets=[_, _, *_]):
            raise SyntacticallyExcluded(s, "multiple assignment targets")
        case ast.Assign(targets=[ast.Subscript()]):
            raise SyntacticallyExcluded(s, "item assignment")
        case ast.Assign(targets=[ast.Attribute()]):
            raise SyntacticallyExcluded(s, "attribute assignment")
        case ast.Assign(targets=[ast.Name(id=x)], value=e):
            return Syntax.StmtAssign(x, Option.None_(), expr(e))
        case ast.Assign():
            raise SyntacticallyExcluded(s, "unpacking assignment")
        case ast.AnnAssign(target=ast.Name(id=x), annotation=a, value=None):
            return Syntax.StmtDeclare(x, annotation(a))
        case ast.AnnAssign(target=ast.Name(id=x), annotation=a, value=ast.expr() as e):
            psi = annotation(a)
            return Syntax.StmtAssign(x, Option.Some(psi), expr(e))
        case ast.AnnAssign():
            raise SyntacticallyExcluded(s, "assignment target other than a simple name")
        case ast.Expr(value=e):
            return Syntax.StmtExpr(expr(e))
        case ast.Assert(test=e, msg=e_):
            e_t = expr(e)
            return Syntax.StmtAssert(e_t, option(None if e_ is None else expr(e_)))
        case ast.Return(value=e):
            return Syntax.StmtReturn(option(None if e is None else expr(e)))
        case ast.If(test=e, body=ss, orelse=ss_):
            e_t = expr(e)
            ss_t = seq(ss)
            elifs, else_ = branches(s.col_offset, ss_)
            return Syntax.StmtIf(e_t, ss_t, elifs, else_)
        case ast.Match(subject=e, cases=bs):
            e_t = expr(e)
            return Syntax.StmtMatch(e_t, [match_case(b) for b in bs])
        case ast.AugAssign():
            raise SyntacticallyExcluded(s, "augmented assignment (+=, etc.)")
        case ast.Delete():
            raise SyntacticallyExcluded(s, "del")
        case ast.For():
            raise SyntacticallyExcluded(s, "for loops")
        case ast.While():
            raise SyntacticallyExcluded(s, "while loops")
        case ast.With():
            raise SyntacticallyExcluded(s, "with statements")
        case ast.AsyncFunctionDef() | ast.AsyncFor() | ast.AsyncWith():
            raise SyntacticallyExcluded(s, "async")
        case ast.Raise():
            raise SyntacticallyExcluded(s, "raise")
        case ast.Try() | ast.TryStar():
            raise SyntacticallyExcluded(s, "try/except")
        case ast.Import() | ast.ImportFrom():
            raise SyntacticallyExcluded(s, "import outside the module top level")
        case ast.Global():
            raise SyntacticallyExcluded(s, "global")
        case ast.Nonlocal():
            raise SyntacticallyExcluded(s, "nonlocal")
        case ast.Break():
            raise SyntacticallyExcluded(s, "break")
        case ast.Continue():
            raise SyntacticallyExcluded(s, "continue")
        case _:
            raise SyntacticallyExcluded(s, f"{type(s).__name__} statement")


def match_case(b: ast.match_case) -> tuple[Pat, Stmt]:
    if b.guard is not None:
        raise SyntacticallyExcluded(b, "case guards")
    p = pat(b.pattern)
    dup = duplicate(bound(b.pattern))
    if dup is not None:
        raise PythonRejects(f"duplicate variable {dup} in pattern", *node_position(b.pattern))
    return (p, seq(b.body))


def branches(col: int, orelse: list[ast.stmt]) -> tuple[list[tuple[Expr, Stmt]], Any]:
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


def seq(body: list[ast.stmt]) -> Stmt:
    *ss, s = [item_stmt(item) for item in statements(body)]
    return reduce(lambda s_, s__: seq_stmt(s__, s_), reversed(ss), s)


def seq_stmt(s: Stmt, s_: Stmt) -> Stmt:
    return Positions.At(located_at(s), Syntax.StmtSeq(s, s_))


def item_stmt(item: Statement) -> Stmt:
    match item:
        case ast.stmt():
            return stmt(item)
        case [ast.FunctionDef() as d, *_]:
            return at(d, Syntax.StmtMutualRegion([func(d_) for d_ in item]))
        case [ast.ClassDef() as chi, *_]:
            raise SyntacticallyExcluded(chi, "class definition outside the module top level")
        case [chi, *_]:
            raise SyntacticallyExcluded(chi, "type statement outside the module top level")
        case _:
            raise AssertionError("empty region")


def func(d: ast.stmt) -> Func:
    assert isinstance(d, ast.FunctionDef)  # mutual def regions hold only def statements
    alphas = type_params(d)
    args = params(d.args)
    if len(d.decorator_list) > 0:
        raise SyntacticallyExcluded(d, "decorators")
    if any(a.annotation is None for a in args):
        raise SyntacticallyExcluded(d, "unannotated parameter")
    if d.returns is None:
        raise SyntacticallyExcluded(d, "unannotated return type")
    tau = annotation(d.returns)
    xs = [(a.arg, annotation(a.annotation)) for a in args]
    return at(d, Syntax.Def(d.name, alphas, xs, tau, seq(d.body)))


def type_params(node: ast.FunctionDef | ast.ClassDef | ast.TypeAlias) -> list[str]:
    alphas = [type_param(param) for param in node.type_params]
    dup = duplicate(alphas)
    if dup is not None:
        raise PythonRejects(f"duplicate type parameter {dup}", *node_position(node))
    return alphas


def type_param(param: ast.type_param) -> str:
    match param:
        case ast.TypeVar(name=alpha, bound=ast.Tuple()):
            raise SyntacticallyExcluded(param, f"constraints on type parameter {alpha}")
        case ast.TypeVar(name=alpha, bound=None):
            return alpha
        case ast.TypeVar(name=alpha):
            raise SyntacticallyExcluded(param, f"bound on type parameter {alpha}")
        case ast.ParamSpec(name=alpha):
            raise SyntacticallyExcluded(param, f"ParamSpec type parameter **{alpha}")
        case ast.TypeVarTuple(name=alpha):
            raise SyntacticallyExcluded(param, f"TypeVarTuple type parameter *{alpha}")
        case _:
            raise AssertionError(f"unexpected type parameter: {type(param).__name__}")


def type_def(chi: ast.stmt) -> TypeDef:
    return at(chi, type_def_node(chi))


def type_def_node(chi: ast.stmt) -> TypeDef:
    match chi:
        case ast.ClassDef(
            name=c, bases=bases, body=body, decorator_list=decorators, keywords=keywords
        ):
            if any(isinstance(b, ast.Name) and b.id == "Enum" for b in bases):
                raise SyntacticallyExcluded(chi, "enum classes")
            alphas = type_params(chi)
            match decorators:
                case []:
                    raise SyntacticallyExcluded(chi, "undecorated class")
                case [ast.Name(id="dataclass")]:
                    pass
                case [_]:
                    raise SyntacticallyExcluded(chi, "class decorator other than @dataclass")
                case _:
                    raise SyntacticallyExcluded(chi, "multiple class decorators")
            base = extends(chi, bases)
            if len(keywords) > 0:
                raise SyntacticallyExcluded(chi, "class keyword arguments")
            match body:
                case [ast.Pass()]:
                    fields = []
                case _:
                    fields = [field(t) for t in body]
            return Syntax.Dataclass(c, alphas, base, fields)
        case ast.TypeAlias(name=ast.Name(id=x), value=psi):
            alphas = type_params(chi)
            return Syntax.TypeStmt(x, alphas, annotation(psi))
        case _:
            raise AssertionError(f"unexpected type definition: {type(chi).__name__}")


def field(t: ast.stmt) -> tuple[str, TyExpr]:
    match t:
        case ast.AnnAssign(target=ast.Name(id=x), annotation=a, value=None):
            return (x, annotation(a))
        case ast.AnnAssign(target=ast.Name(), value=ast.expr()):
            raise SyntacticallyExcluded(t, "field default values")
        case ast.AnnAssign():
            raise SyntacticallyExcluded(t, "field target other than a simple name")
        case _:
            raise SyntacticallyExcluded(t, "dataclass member other than a field declaration")


def extends(chi: ast.ClassDef, bases: list[ast.expr]) -> Any:
    match bases:
        case []:
            return Option.None_()
        case [b]:
            match ty_expr(b):
                case Syntax.TyExprName(q, args):
                    return Option.Some((q, args))
                case _:
                    raise SyntacticallyExcluded(
                        b, "base class other than a name, optionally applied to type arguments"
                    )
        case _:
            raise SyntacticallyExcluded(chi, "multiple inheritance")


def top_stmt(body: list[ast.stmt]) -> TopStmt:
    *ss, s = [top_item(item) for item in statements(body)]
    return reduce(lambda s_, s__: Syntax.TopSeq(s__, s_), reversed(ss), s)


def top_item(item: Statement) -> TopStmt:
    match item:
        case [ast.ClassDef() | ast.TypeAlias(), *_]:
            return Syntax.TypeDefs([type_def(chi) for chi in item])
        case ast.stmt() if is_import(item):
            raise SyntacticallyExcluded(item, "import after another statement")
        case ast.stmt() if len(returns_outside_function(item)) > 0:
            raise PythonRejects(
                "return outside a function", *node_position(returns_outside_function(item)[0])
            )
        case _:
            return Syntax.Stmt(item_stmt(item))


def returns_outside_function(s: ast.stmt) -> list[ast.Return]:
    """Return statements of a top-level statement s"""
    match s:
        case ast.Return():
            return [s]
        case ast.If(body=ss, orelse=ss_):
            return [r for s_ in ss + ss_ for r in returns_outside_function(s_)]
        case ast.Match(cases=cases):
            return [r for case in cases for s_ in case.body for r in returns_outside_function(s_)]
        case _:
            return []


def import_(iota: ast.stmt) -> Import:
    return at(iota, import_node(iota))


def import_node(iota: ast.stmt) -> Import:
    match iota:
        case ast.Import(names=[ast.alias(name=q, asname=None)]):
            return Syntax.Import(qualified_name(parse_name(q)))
        case ast.Import(names=[_]):
            raise SyntacticallyExcluded(iota, "import-as")
        case ast.Import():
            raise SyntacticallyExcluded(iota, "multi-target import (import a, b)")
        case ast.ImportFrom(names=[]):
            raise SyntacticallyExcluded(iota, "empty name list")
        case ast.ImportFrom(level=int() as level) if level > 0:
            raise SyntacticallyExcluded(iota, "relative imports")
        case ast.ImportFrom(module=str(q), names=aliases):
            for alias in aliases:
                if alias.name == "*":
                    raise SyntacticallyExcluded(iota, "from M import *")
                if alias.asname is not None:
                    raise SyntacticallyExcluded(iota, "from-import-as")
            return Syntax.FromImport(qualified_name(parse_name(q)), [a.name for a in aliases])
        case _:
            raise AssertionError(f"unexpected import: {type(iota).__name__}")


def name_declaration(q: Name) -> ast.stmt:
    return ast.parse(f"__name__: str = {'.'.join(q)!r}").body[0]


def module_body(q: Name, m: ast.Module) -> ModuleBody:
    iotas, stmts = split_imports(m.body)
    imports = [import_(iota) for iota in iotas]
    return Syntax.ModuleBody(imports, top_stmt([name_declaration(q), *stmts]))


def parse_module(source: str, filename: str, q: Name) -> ModuleBody:
    try:
        m = parse(source, filename)
    except SyntaxError as e:
        raise python_rejects(e) from e
    return module_body(q, m)
