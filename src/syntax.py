import ast
import sys
from collections.abc import Callable

from aux import is_import, split_imports
from type_syntax import parse_annotation

OP_SYMBOLS: dict[type, str] = {
    ast.BitOr: "|",
    ast.BitAnd: "&",
    ast.BitXor: "^",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.MatMult: "@",
    ast.Invert: "~",
}


class Unsupported(Exception):
    exit_code: int  # overridden by subclass
    msg: str

    def __init__(self, node: ast.AST, msg: str):
        self.line: int | None = getattr(node, "lineno", None)
        self.col: int | None = getattr(node, "col_offset", None)
        self.msg = msg
        super().__init__(msg)


class Prohibited(Unsupported):
    exit_code = 1


class NotYetSupported(Unsupported):
    exit_code = 2

    def __init__(self, node: ast.AST, feature: str, issue: int):
        super().__init__(node, f"{feature} not yet supported (#{issue})")


class PatList(ast.MatchSequence):
    pass


class PatTuple(ast.MatchSequence):
    pass


def map_tree(f: Callable[[ast.AST], ast.AST], node: ast.AST) -> ast.AST:
    """Rebuild node bottom-up, applying f to each node. Subtrees f leaves alone are shared, not copied."""
    fields: dict[str, object] = {}
    for name in node._fields:
        v = getattr(node, name)
        match v:
            case ast.AST():
                fields[name] = map_tree(f, v)
            case list():
                new = [map_tree(f, x) if isinstance(x, ast.AST) else x for x in v]
                fields[name] = v if all(a is b for a, b in zip(new, v)) else new
            case _:
                fields[name] = v
    unchanged = all(fields[name] is getattr(node, name) for name in node._fields)
    return f(node if unchanged else ast.copy_location(type(node)(**fields), node))


def classify_sequence(source: str) -> Callable[[ast.AST], ast.AST]:
    """Python's parser gives list and tuple patterns one node type; the source text tells them apart."""

    def classify(node: ast.AST) -> ast.AST:
        if not isinstance(node, ast.MatchSequence):
            return node
        segment = ast.get_source_segment(source, node)
        assert segment is not None
        cls = PatList if segment.startswith("[") else PatTuple
        return ast.copy_location(cls(patterns=node.patterns), node)

    return classify


def parse(source: str, filename: str) -> ast.Module:
    m = map_tree(classify_sequence(source), ast.parse(source, filename=filename))
    assert isinstance(m, ast.Module)
    return m


def check_syntax_stmt(node: ast.stmt) -> None:
    match node:
        case ast.Pass():
            pass
        case ast.Assign():
            if len(node.targets) != 1:
                raise Prohibited(node, "multiple assignment targets")
            target = node.targets[0]
            match target:
                case ast.Subscript():
                    raise Prohibited(node, "item assignment prohibited")
                case ast.Attribute():
                    raise Prohibited(node, "attribute assignment prohibited")
                case ast.Name():
                    check_syntax_expr(node.value)
                case _:
                    raise NotYetSupported(node, "destructuring assignment", 54)
        case ast.Return():
            if node.value is not None:
                check_syntax_expr(node.value)
        case ast.If():
            check_syntax_expr(node.test)
            check_syntax_body(node.body)
            check_syntax_body(node.orelse)
        case ast.FunctionDef():
            check_syntax_arguments(node.args)
            if len(node.decorator_list) > 0:
                raise NotYetSupported(node, "decorators", 58)
            if any(a.annotation is None for a in node.args.args):
                raise Prohibited(node, "parameters must be annotated")
            if node.returns is None:
                raise Prohibited(node, "return type must be annotated")
            check_syntax_annotation(node.returns)
            check_syntax_body(node.body)
        case ast.Expr():
            check_syntax_expr(node.value)
        case ast.Assert():
            check_syntax_expr(node.test)
            if node.msg is not None:
                check_syntax_expr(node.msg)
        case ast.AugAssign():
            raise Prohibited(node, "augmented assignment (+=, etc.) prohibited")
        case ast.AnnAssign():
            if node.value is None:
                raise Prohibited(node, "annotation without assignment prohibited")
            if not isinstance(node.target, ast.Name):
                raise Prohibited(node, "assignment target must be a simple name")
            check_syntax_annotation(node.annotation)
            check_syntax_expr(node.value)
        case ast.Delete():
            raise Prohibited(node, "del prohibited")
        case ast.For():
            raise Prohibited(node, "for loops prohibited")
        case ast.While():
            raise Prohibited(node, "while loops prohibited")
        case ast.With():
            raise Prohibited(node, "with statements prohibited")
        case ast.AsyncFunctionDef():
            raise Prohibited(node, "async prohibited")
        case ast.AsyncFor():
            raise Prohibited(node, "async prohibited")
        case ast.AsyncWith():
            raise Prohibited(node, "async prohibited")
        case ast.Raise():
            raise Prohibited(node, "raise prohibited")
        case ast.Try():
            raise Prohibited(node, "try/except prohibited")
        case ast.Import():
            raise Prohibited(node, "import only allowed at module top level")
        case ast.ImportFrom():
            raise Prohibited(node, "import only allowed at module top level")
        case ast.Global():
            raise Prohibited(node, "global prohibited")
        case ast.Nonlocal():
            raise Prohibited(node, "nonlocal prohibited")
        case ast.ClassDef():
            raise Prohibited(node, "class declaration only at module top level")
        case ast.Match():
            check_syntax_expr(node.subject)
            for case in node.cases:
                if case.guard is not None:
                    raise NotYetSupported(case, "case guards", 190)
                check_syntax_pattern(case.pattern)
                check_syntax_body(case.body)
        case ast.Break():
            raise Prohibited(node, "break prohibited")
        case ast.Continue():
            raise Prohibited(node, "continue prohibited")
        case _:
            raise Prohibited(node, f"unknown statement type: {type(node).__name__}")


def check_syntax_classdef(node: ast.ClassDef) -> None:
    if any(isinstance(b, ast.Name) and b.id == "Enum" for b in node.bases):
        raise NotYetSupported(node, "enum classes", 86)
    if len(node.decorator_list) != 1:
        raise Prohibited(node, "class must have exactly the @dataclass decorator")
    deco = node.decorator_list[0]
    if not (isinstance(deco, ast.Name) and deco.id == "dataclass"):
        raise Prohibited(node, "only the @dataclass decorator is supported on classes")
    if len(node.bases) > 1:
        raise Prohibited(node, "multiple inheritance prohibited")
    if len(node.bases) > 0 and not isinstance(node.bases[0], ast.Name):
        raise Prohibited(node, "base class must be a simple name")
    if len(node.keywords) > 0:
        raise Prohibited(node, "class keyword arguments prohibited")
    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
        return
    for stmt in node.body:
        check_syntax_field(stmt)


def check_syntax_field(stmt: ast.stmt) -> None:
    if not isinstance(stmt, ast.AnnAssign):
        raise Prohibited(stmt, "dataclass body may contain only field declarations")
    if not isinstance(stmt.target, ast.Name):
        raise Prohibited(stmt, "field target must be a simple name")
    if stmt.value is not None:
        raise Prohibited(stmt, "field default values prohibited")
    check_syntax_annotation(stmt.annotation)


def check_syntax_pattern(node: ast.pattern) -> None:
    match node:
        case ast.MatchValue():
            v = node.value
            match v:
                case ast.Constant():
                    if isinstance(v.value, (int, float, str)):
                        return
                case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=value)):
                    if isinstance(value, (int, float)):
                        return
                case ast.Attribute():
                    raise NotYetSupported(node, "attribute value patterns", 86)
            raise Prohibited(node, "complex and bytes literal patterns prohibited")
        case ast.MatchSingleton():
            pass
        case ast.MatchAs():
            if node.pattern is not None:
                check_syntax_pattern(node.pattern)
        case ast.MatchSequence():
            for p in node.patterns:
                check_syntax_pattern(p)
        case ast.MatchClass():
            for p in list(node.patterns) + list(node.kwd_patterns):
                check_syntax_pattern(p)
        case ast.MatchMapping():
            if node.rest is not None:
                raise NotYetSupported(node, "rest capture in dict patterns", 84)
            for key in node.keys:
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    raise Prohibited(key, "dict pattern keys must be string literals")
            for sub in node.patterns:
                check_syntax_pattern(sub)
        case ast.MatchOr():
            raise NotYetSupported(node, "or-patterns", 85)
        case ast.MatchStar():
            raise NotYetSupported(node, "star patterns", 84)
        case _:
            raise Prohibited(node, f"unknown pattern type: {type(node).__name__}")


def check_syntax_expr(node: ast.expr) -> None:
    match node:
        case ast.Constant():
            if isinstance(node.value, (int, float, str, bool, type(None))):
                return
            if isinstance(node.value, (bytes, complex)):
                raise Prohibited(node, f"{type(node.value).__name__} literals prohibited")
            raise Prohibited(node, f"prohibited literal type: {type(node.value).__name__}")
        case ast.Name():
            pass
        case ast.BinOp():
            allowed = (
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.FloorDiv,
                ast.Mod,
                ast.Pow,
            )
            if not isinstance(node.op, allowed):
                sym = OP_SYMBOLS.get(type(node.op), type(node.op).__name__)
                raise Prohibited(node, f"binary operator '{sym}' prohibited")
            check_syntax_expr(node.left)
            check_syntax_expr(node.right)
        case ast.UnaryOp():
            if isinstance(node.op, (ast.Not, ast.UAdd, ast.USub)):
                check_syntax_expr(node.operand)
                return
            sym = OP_SYMBOLS.get(type(node.op), type(node.op).__name__)
            raise Prohibited(node, f"unary operator '{sym}' prohibited")
        case ast.BoolOp():
            if len(node.values) > 2:
                raise NotYetSupported(node, "chained boolean operator", 82)
            for v in node.values:
                check_syntax_expr(v)
        case ast.Compare():
            if len(node.ops) > 1:
                raise NotYetSupported(node, "chained comparison", 82)
            for op in node.ops:
                if isinstance(op, (ast.Is, ast.IsNot)):
                    raise NotYetSupported(node, "identity operator (is/is not)", 81)
            check_syntax_expr(node.left)
            for c in node.comparators:
                check_syntax_expr(c)
        case ast.Call():
            check_syntax_expr(node.func)
            for a in node.args:
                check_syntax_expr(a)
            for k in node.keywords:
                check_syntax_keyword(k)
        case ast.IfExp():
            check_syntax_expr(node.test)
            check_syntax_expr(node.body)
            check_syntax_expr(node.orelse)
        case ast.Lambda():
            check_syntax_arguments(node.args)
            check_syntax_expr(node.body)
        case ast.List():
            for e in node.elts:
                check_syntax_expr(e)
        case ast.Tuple():
            for e in node.elts:
                check_syntax_expr(e)
        case ast.Dict():
            for key in node.keys:
                if key is None:
                    raise Prohibited(node, "dict unpacking prohibited")
                check_syntax_expr(key)
            for v in node.values:
                check_syntax_expr(v)
        case ast.Set():
            raise NotYetSupported(node, "set literals", 147)
        case ast.Attribute():
            check_syntax_expr(node.value)
        case ast.Subscript():
            check_syntax_expr(node.value)
            check_syntax_expr(node.slice)
        case ast.ListComp():
            check_syntax_expr(node.elt)
            for g in node.generators:
                check_syntax_generator(g)
        case ast.DictComp():
            check_syntax_expr(node.key)
            check_syntax_expr(node.value)
            for g in node.generators:
                check_syntax_generator(g)
        case ast.SetComp():
            raise NotYetSupported(node, "set comprehensions", 147)
        case ast.Slice():
            raise NotYetSupported(node, "slicing", 59)
        case ast.GeneratorExp():
            raise Prohibited(node, "generator expressions prohibited")
        case ast.NamedExpr():
            raise Prohibited(node, "walrus operator (:=) prohibited")
        case ast.Starred():
            raise Prohibited(node, "starred expressions prohibited")
        case ast.Await():
            raise Prohibited(node, "async prohibited")
        case ast.Yield():
            raise Prohibited(node, "yield prohibited")
        case ast.YieldFrom():
            raise Prohibited(node, "yield prohibited")
        case ast.JoinedStr():
            raise NotYetSupported(node, "f-strings", 55)
        case ast.FormattedValue():
            raise NotYetSupported(node, "f-strings", 55)
        case _:
            raise Prohibited(node, f"unknown expression type: {type(node).__name__}")


def check_syntax_body(stmts: list[ast.stmt]) -> None:
    for s in stmts:
        check_syntax_stmt(s)


def check_syntax_import(node: ast.stmt) -> None:
    match node:
        case ast.Import():
            if len(node.names) != 1:
                raise NotYetSupported(node, "multi-target import (import a, b)", 135)
            if node.names[0].asname is not None:
                raise NotYetSupported(node, "import-as", 135)
        case ast.ImportFrom():
            if len(node.names) == 0:
                raise Prohibited(node, "empty name list")
            if node.level > 0:
                raise NotYetSupported(node, "relative imports", 126)
            assert node.module is not None  # absent only in a relative import
            for alias in node.names:
                if alias.name == "*":
                    raise NotYetSupported(node, "from M import *", 105)
                if alias.asname is not None:
                    raise NotYetSupported(node, "from-import-as", 135)
        case _:
            raise AssertionError(f"unexpected statement: {type(node).__name__}")


def check_syntax_top_level(body: list[ast.stmt]) -> None:
    iotas, stmts = split_imports(body)
    for iota in iotas:
        check_syntax_import(iota)
    for s in stmts:
        if is_import(s):
            raise Prohibited(s, "imports must precede all other statements")
        if isinstance(s, ast.ClassDef):
            check_syntax_classdef(s)
        else:
            check_syntax_stmt(s)


def check_syntax_keyword(node: ast.keyword) -> None:
    check_syntax_expr(node.value)


def check_syntax_generator(node: ast.comprehension) -> None:
    if node.is_async:
        raise Prohibited(node, "async comprehensions prohibited")
    if not isinstance(node.target, ast.Name):
        raise NotYetSupported(node, "destructuring in comprehensions", 54)
    check_syntax_expr(node.iter)
    for i in node.ifs:
        check_syntax_expr(i)


def check_syntax_annotation(node: ast.expr | None) -> None:
    if node is not None and parse_annotation(node) is None:
        raise Prohibited(node, "unsupported type annotation")


def check_syntax_arguments(node: ast.arguments) -> None:
    if node.vararg is not None:
        raise NotYetSupported(node, "*args", 57)
    if node.kwarg is not None:
        raise NotYetSupported(node, "**kwargs", 57)
    if len(node.kwonlyargs) > 0:
        raise Prohibited(node, "keyword-only arguments prohibited")
    if len(node.defaults) > 0:
        raise NotYetSupported(node, "default arguments", 56)
    if len(node.kw_defaults) > 0:
        raise NotYetSupported(node, "default arguments", 56)
    if len(node.posonlyargs) > 0:
        raise Prohibited(node, "positional-only arguments prohibited")
    for a in node.args:
        check_syntax_annotation(a.annotation)


def check_syntax_module(node: ast.Module) -> Unsupported | None:
    try:
        check_syntax_top_level(node.body)
        return None
    except Unsupported as e:
        return e


def check_file(filename: str) -> Unsupported | None:
    with open(filename) as f:
        source = f.read()
    return check_syntax_module(parse(source, filename))


def format_result(result: Unsupported | None, filename: str) -> str:
    if result is None:
        return f"{filename}: ok"
    if result.line is not None:
        return f"{filename}:{result.line}:{result.col}: {result.msg}"
    return f"{filename}: {result.msg}"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: syntax.py <file.py> [<file.py> ...]")
        sys.exit(1)
    exit_code = 0
    for filename in sys.argv[1:]:
        result = check_file(filename)
        print(format_result(result, filename))
        if result is not None:
            exit_code = result.exit_code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
